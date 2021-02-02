# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: delete_line.py
@time: 2021/1/13 11:51
@desc: 根据流水线名称和类型，批量删除流水线
'''
import time, requests, json, sys, logging
import threading
from Queue import Queue
from ast import literal_eval

from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()
reload(sys)
sys.setdefaultencoding('utf8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

tool_headers = {
    "host": "tool.easyops-only.com",
    "org": "3087",
    "user": "easyops",
    "content-Type": "application/json"
}
cmdb_headers = {
    "content-Type": "application/json",
    "host": "cmdb_resource.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

cmdb_host = "10.163.128.232"

remove_line = '测试环境部署(Fcode)'  # 需要删除的流水线名称
# test, production development
line_type = "test"

# 携程池
n = 1  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)


def http_post(method, url, params=None, headers=cmdb_headers):
    if method == 'POST':
        r = requests.post(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                ret = json.loads(r.content)['data']
                return ret['list']
            except Exception as e:
                return json.loads(r.content)
        else:
            return json.loads(r.content)

    elif method == 'POSTS':
        try:
            page_size = 100
            params['page'] = 1
            params['page_size'] = page_size
            ret_list = []
            while True:
                r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    one_ret = json.loads(r.content)['data']['list']  # 第一次获取的数据

                    if len(one_ret) == 0:
                        break

                    if len(one_ret) <= page_size:
                        params['page'] += 1
                        ret_list += one_ret
                    else:
                        break
            return ret_list
        except Exception as e:
            return []

    elif method == 'PUT':
        r = requests.put(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                ret = json.loads(r.content)['data']
                code = str(json.loads(r.content)['code'])
            except Exception as e:
                ret = json.loads(r.content)
                code = '1'
            return code, ret

    elif method == 'GET':
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            ret = json.loads(r.content)['data']
            return ret

    elif method in ("repo",):
        try:
            r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                if data.get('code') == 0:
                    return r.content
                else:
                    return False
        except Exception as e:
            return False

    elif method in ('DELETE', 'delete'):
        try:
            r = requests.delete(url, headers=headers, data=json.dumps(params), timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                return data.get('code')
            else:
                return r.content
        except Exception as e:
            return e


class DeleteLineDemo(object):
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    # 删除流水线
    def delete_line(self, flowId):
        url = "http://{HOST}/flows/{ID}".format(HOST=cmdb_host, ID=flowId)
        ret = http_post('delete', url, headers=tool_headers)
        return ret

    # 更新应用里面的pipline
    def update_app(self, instanceId, pipline_list):
        url = "http://{HOST}/object/APP/instance/{id}".format(HOST=cmdb_host, id=instanceId)
        # pipline_list['delete_line'] = True
        code, ret = http_post('PUT', url, params=pipline_list)
        if code == '0':
            logging.info('Pipline successfully updated')
        else:
            logging.error('Failed to update application pipeline')

    def getData(self):
        """
        获取平台所有自研应用，初始化了流水线模板的应用
        :return:
        """
        logging.info('Start getting app information....')
        url = 'http://{HOST}/object/APP/instance/_search'.format(HOST=cmdb_host)
        params = {
            "query": {
                # "self_research": {
                #     "$eq": "是"
                # },
                # "init_tem": {
                #     "$eq": True
                # },
                "name": {
                    "$eq": "itc-coa_itc-coa-service"
                }
            },
            "fields": {"name": True, "__pipeline": True}
        }
        logging.info('search app params : %s' % params)
        app_data_list = http_post('POSTS', url, params=params)
        result = [app_data_list[i:i + n] for i in range(0, len(app_data_list), n)]
        logging.info('应用信息共获取{}组数据,每组{}个元素'.format(len(result), n))

        return result

    def dealdata(self, content):
        res = []
        for data in content:
            res.append(pool.spawn(self.gevent_data, data))
        gevent.joinall(res)

        logging.info('------------------------------------------------------')

    def gevent_data(self, data):
        name = data.get('name')  # 应用名称
        logging.info('app name is : %s' % name)

        # 1. 先判断__pipeline 是否存在
        if not dict(data).has_key('__pipeline'):
            logging.warning(data)
            return

        # 2. 获取instanceId, __pipeline
        clear_line_dict = {}
        clear_line_list = []  # 剔除完多余的line，需要重新修改应用
        __pipeline = data.get('__pipeline')
        instanceId = data.get('instanceId')

        remove_flowId = ''  # 需要处理的应用流水线流程id
        for line in __pipeline:
            try:
                metadata_data = json.loads(line.get('metadata'))  # metadata是json
                metadata_type = metadata_data.get('type')
                if metadata_type == line_type:  # 先判断流水线类型，开发，测试，生产
                    line_name = str(line.get('name'))  # 应用的流水线名称
                    if str(remove_line) in line_name:  # 判断流水线名称是否相等
                        remove_flowId = line.get('flowId')
                        continue
                clear_line_list.append(line)  # 将line保存到新的列表中
            except Exception as e:
                logging.info('查询应用流水线报错:%s' % str(e))
                continue

        logging.info('need remove_flowId: %s' % remove_flowId)
        clear_line_dict["__pipeline"] = clear_line_list  # 组合成k，格式，后续批量修改应用pipline

        if remove_flowId:
            logging.info('Start the delete process to delete the template with the latest data')
            code = self.delete_line(remove_flowId)
            if code == 0:
                logging.info('Update process succeeded')
            else:
                logging.error('Failed to apply update process')

            logging.info('Need to insert__pipeline info : %s' % clear_line_dict)
            self.update_app(instanceId, clear_line_dict)

        # else:
        #     url = "http://{HOST}/object/APP/instance/{id}".format(HOST=cmdb_host, id=instanceId)
        #     code, ret = http_post('PUT', url, params={"delete_line": True})
        #     if code == '0':
        #         logging.info('delete_line successfully updated')
        #     else:
        #         logging.error('delete_line to update application pipeline')

    # 开启多线程任务
    def task(self):
        # 设定最大队列数和线程数
        q = Queue(maxsize=10)
        while self.data:
            content = self.data.pop()
            t = threading.Thread(target=self.dealdata, args=(content,))
            q.put(t)
            if (q.full() == True) or (len(self.data)) == 0:
                thread_list = []
                while q.empty() == False:
                    t = q.get()
                    thread_list.append(t)
                    t.start()
                for t in thread_list:
                    t.join()


if __name__ == '__main__':
    DeleteLineDemo()
