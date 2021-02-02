# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: update_process.py
@time: 2021/1/13 11:51
@desc: 更新流水线
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

cmdb_host = "10.163.128.232"
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

#input_tmp_name = "生产环境灰度部署(Fcode)"

if input_tmp_name == "生产环境灰度部署(Fcode)":
    tmp_line_id = 'da108c1793dfddd6205cebaf4dfed6fb'  # 流水线模板ID
    tmp_line_name = input_tmp_name
    # test, production, development
    tmp_line_type = "production"

elif input_tmp_name == "生产环境全量部署(Fcode)":
    tmp_line_id = 'aee5f123ec1f34e35947342ce02a1644'  # 流水线模板ID
    tmp_line_name = input_tmp_name
    # test, production, development
    tmp_line_type = "production"

elif input_tmp_name == "开发环境部署(Fcode)":
    tmp_line_id = '2f947aebbaf72920533fd7f76e949c35'  # 流水线模板ID
    tmp_line_name = input_tmp_name
    # test, production, development
    tmp_line_type = "development"

else:
    tmp_line_id = '3c45b463ea3c3b027e93a07290c1ce99'  # 流水线模板ID
    tmp_line_name = input_tmp_name
    # test, production, development
    tmp_line_type = "test"

# 携程池
n = 1  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

logging.info('The name of the template that started the synchronization update: %s' % tmp_line_name)
logging.info('The ID of the template that started the synchronization update: %s' % tmp_line_id)
logging.info('Type of template to start synchronous update: %s' % tmp_line_type)


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


class UpdateLineDemo(object):
    def __init__(self):
        self.get_tmp_info()  # 获取流水线模板信息
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    # 1.先获取流水线模板信息
    def get_tmp_info(self):
        """
        获取流水线模板信息
        :return:
        """
        url = 'http://{HOST}/flows/{TMP}'.format(HOST=cmdb_host, TMP=tmp_line_id)
        tmp_data = http_post('GET', url, headers=tool_headers)
        self.version = tmp_data.get('version')  # 获取最新的模板版本ID
        stepList = tmp_data.get('stepList')  # 获取stepList
        metadata = tmp_data.get('metadata')  # metadata
        flowInputs = tmp_data.get('flowInputs')  # flowInputs
        flowOutputs = tmp_data.get('flowOutputs')  # flowOutputs
        outputDefs = tmp_data.get('outputDefs')  # outputDefs
        self.tmp_data = {
            "stepList": stepList,
            "flowInputs": flowInputs,
            "flowOutputs": flowOutputs,
            "outputDefs": outputDefs,
            "category": "app_pipeline",
            # "metadata": metadata
        }
        logging.info('Latest template ID of pipeline: %s' % self.version)
        return self.tmp_data

    # 2. 更新流水线流水线信息
    def update_line(self, data, flowId):
        url = "http://{HOST}/flows/{ID}".format(HOST=cmdb_host, ID=flowId)
        response = requests.request("PUT", url, headers=tool_headers, data=json.dumps(data))
        data = json.loads(response.text.encode('utf8'))
        logging.info('update_line ret: %s' % data)
        code = str(data.get('code', ''))
        return code

    # 更新应用里面的pipline
    def update_app(self, instanceId, new_line_list):
        url = "http://{HOST}/object/APP/instance/{id}".format(HOST=cmdb_host, id=instanceId)
        params = {
            "__pipeline": new_line_list,
            "update_tmp": True
        }
        code, ret = http_post('PUT', url, params=params)
        if code == '0':
            logging.info('App Pipline successfully updated')
        else:
            logging.error('App Failed to update application pipeline')

    def getData(self):
        """
        获取平台所有自研应用，初始化了流水线模板的应用
        :return:
        """
        logging.info('Start getting app information....')
        url = 'http://{HOST}/object/APP/instance/_search'.format(HOST=cmdb_host)
        if input_app_name:
            params = {
                "query": {
                    "self_research": {
                        "$eq": "是"
                    },
                    # "init_tem": {
                    #     "$eq": True
                    # },
                    # "update_tmp": {
                    #     "$eq": False
                    # },
                    "name": {
                        "$eq": input_app_name
                    },

                },
                "fields": {"name": True, "__pipeline": True}
            }
        else:
            params = {
                "query": {
                    "self_research": {
                        "$eq": "是"
                    },
                    # "init_tem": {
                    #     "$eq": True
                    # },
                    # "update_tmp": {
                    #     "$eq": False
                    # },
                    # "name": {
                    #     "$eq": "fcodeTest20201230"
                    # },

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

    def gevent_data(self, data):
        name = data.get('name')  # 应用名称
        logging.info('app name is : %s' % name)

        # 1. 先判断__pipeline 是否存在
        if not dict(data).has_key('__pipeline'):
            logging.warning(data)
            return

        # 2. 获取instanceId, __pipeline
        __pipeline = data.get('__pipeline')
        instanceId = data.get('instanceId')
        for line in __pipeline:
            line_templateVersion = line.get('templateVersion')  # 流水线版本最新id
            line_templateId = line.get('templateId')  # 流水线版本ID
            line_flowId = line.get('flowId')  # 流程id
            metadata = line.get('metadata')  # metadata
            metadata_type = json.loads(metadata).get('type')

            # 判断应用里面的流水线名称和模板id是否相同
            if not (line.get('name',
                             '') == tmp_line_name and line_templateId == tmp_line_id and tmp_line_type == metadata_type):
                logging.warning('Pipeline template id not updated')
                continue

            # 判断应用里面的流程id和模板id是否一致，如果不一致需要修改
            if int(line_templateVersion) == int(self.version):
                logging.warning('If the templateVersionID is consistent, it does not need to be updated')
                continue

            # 走到这里就是要同步模板信息
            logging.info('Pipeline template id need updated')
            # 1.更新下metadata 到模板内容中

            # metadata = json.loads(metadata)
            # self.tmp_data['metadata'] = json.dumps(metadata)

            line['templateVersion'] = self.version  # 修改当条templateVersion id
            logging.info('Pipeline template id need updated version: %s' % self.version)
            logging.info('Pipeline template id need updated flowId: %s' % line_flowId)

            # 2. 更新流程update_line ret
            code = self.update_line(self.tmp_data, line_flowId)
            if code == '0':
                logging.info('Update pipeline successfully')
                logging.info('Need to insert app __pipeline info : %s' % __pipeline)
                self.update_app(instanceId, __pipeline)
            else:
                logging.error('Failed to update pipeline')

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
    UpdateLineDemo()
