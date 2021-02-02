# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: delete_line.py
@time: 2021/1/13 11:51
@desc: 根据模板名称批量创建流水线，如果应用流水线存在，则跳过创建
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

create_line = '测试环境部署(Fcode)'  # 需要删除的流水线名称
# test, production development
line_type = "test"

# 携程池
n = 1  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(10)


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


class CreateLineDemo(object):
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def _get_line_tmp(self, app_name, app_instanceId):
        logging.info('------------------------------------------------------------获取流水线模板')
        url = "http://{HOST}/flows?page=1&pageSize=500&category=pipeline_template".format(HOST=cmdb_host)
        logging.info('search tmp url :%s' % url)
        ret = http_post('GET', url, headers=tool_headers)
        tmp_list = ret.get('list')

        tmp_datas = {
            create_line: {}
        }

        tmp_id = {
            create_line: ''
        }

        tmp_versin = {
            create_line: ''
        }

        # 需要跟应用关联的pipline
        focde_list = []
        for tmp in tmp_list:
            name = tmp.get('name')
            if name == create_line:
                metadata = tmp['metadata']
                metadata.update({"appId": app_instanceId})
                tmp['name'] = app_name + '-' + name
                tmp_datas[create_line]['category'] = 'app_pipeline'
                tmp_datas[create_line]['metadata'] = metadata
                tmp_datas[create_line]['name'] = tmp['name']
                tmp_datas[create_line]['stepList'] = tmp['stepList']
                tmp_datas[create_line]['flowOutputs'] = tmp['flowOutputs']
                tmp_id[create_line] = tmp['flowId']
                tmp_versin[create_line] = tmp['version']

        # print json.dumps(tmp_datas['Fcode_Gray_Flow'])
        for k, tmp in tmp_datas.items():
            # 创建测试流程
            try:
                url = 'http://{HOST}/flows'.format(HOST=cmdb_host)
                ret = requests.request("POST", url, headers=tool_headers, data=json.dumps(tmp_datas[k]))
                ret = json.loads(ret.text.encode('utf8'))
                data = ret.get('data')
                flowId = data.get('flowId')  # 流程ID
                # version = data.get('version')

                data = {"flowId": flowId,
                        "metadata": json.dumps({"type": line_type, "appId": app_instanceId}),
                        "name": k, "templateId": tmp_id[k],
                        "templateVersion": tmp_versin[k]}
                focde_list.append(data)

            except Exception as e:
                logging.error('app: %s 获取流水线模板报错:%s' % (app_name, e))

        return focde_list

    # 创建流水线
    def create_pipline(self, app_name, app_instanceId, __pipeline):

        focde_list = self._get_line_tmp(app_name, app_instanceId)

        __pipeline += focde_list
        logging.info('app: %s 应用开始关联流水线，pipline数量:%s' % (app_name, len(__pipeline)))
        # 获取流水线模板信息Fcode_Full_Flow， Fcode_Gray_Flow
        url = 'http://{HOST}/object/APP/instance/{ID}'.format(HOST=cmdb_host, ID=app_instanceId)
        params = {
            "__pipeline": __pipeline,
            "init_tem": True
        }
        ret = requests.request("PUT", url, headers=cmdb_headers, data=json.dumps(params))
        logging.info('app: %s Update pipeline initialization template state: %s' % (app_name, ret))
        if ret.status_code == 200:
            return 0
        else:
            return 1

    def getData(self):
        """
        获取平台所有自研应用，初始化了流水线模板的应用
        :return:
        """
        logging.info('Start getting app information....')
        url = 'http://{HOST}/object/APP/instance/_search'.format(HOST=cmdb_host)
        params = {
            "query": {
                "self_research": {
                    "$eq": "是"
                },
                "init_tem": {
                    "$eq": True
                },
                "name": {
                    "$eq": "itc-coa_itc-coa-service"
                }
            },
            "fields": {"name": True, "__pipeline": True},
            # "page": 1,
            # "page_size": 1
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
        app_name = data.get('name')  # 应用名称
        logging.info('app name is : %s' % app_name)

        # 1. 先判断__pipeline 是否存在
        if not dict(data).has_key('__pipeline'):
            logging.warning('app: %s not __pipeline' % app_name)

        # 2. 获取instanceId, __pipeline
        __pipeline = data.get('__pipeline', [])
        app_instanceId = data.get('instanceId')

        add_tag = True  # 需要处理的应用流水线流程id
        for line in __pipeline:
            try:
                metadata_data = json.loads(line.get('metadata'))  # metadata是json
                metadata_type = metadata_data.get('type')
                if metadata_type == line_type:  # 先判断流水线类型，开发，测试，生产
                    line_name = str(line.get('name'))  # 应用的流水线名称
                    if str(create_line) in line_name:  # 判断流水线名称是否相等,相等的话，不需要创建流水线
                        add_tag = False
                        break
            except Exception as e:
                logging.info('查询应用流水线报错:%s' % str(e))
                continue

        logging.info('Create pipeline ID: %s' % add_tag)

        if add_tag:
            logging.info('Start creating pipeline.........')
            code = self.create_pipline(app_name, app_instanceId, __pipeline)

            if code == 0:
                logging.info('app: %s Update process succeeded' % app_name)
            else:
                logging.error('Failed to apply update process')

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
    CreateLineDemo()
