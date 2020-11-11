# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

# CMDB配置
# easyops_cmdb_host = 'admin.easyops.local'
# easyops_org = '1888'
# easy_user = 'peachtao'
easyops_cmdb_host = '192.168.28.28'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索所有服务节点实例数据
ConfigSWITCHMODEL = '_SERVICENODE'

# 插入数据模型ID
INSERDATAMODEL = 'ORACLE_SERVER'


# 搜索实列列表条件
ConfigParams = {
    "query": {"$and": [{"$or": [{"type": {"$eq": "java"}}]}]},
    "fields": {"instanceId": True, "agentIp": True, "HOST_IP": True, "port": True, "ip": True, "type": True,
               "configInfo": True},
    "only_relation_view": True, "only_my_instance": False
}


# Easyops查询实例
class EasyopsPubic(object):
    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        return self.instance_search(ConfigSWITCHMODEL, ConfigParams)

    # 搜索实例
    def instance_search(self, object_id, params):
        """
        :param object_id: 配置文件中的搜索模型ID
        :param params: 配置文件中的搜索查询条件
        :return:
        """
        if params.has_key('page_size'):
            page_size = 500
        else:
            page_size = 1000
        params['page_size'] = page_size
        params['page'] = 1
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        if not search_result:
            exit('没有查询到数据')

        total_instance_nums = int(search_result['total'])

        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 1):
                params['page'] = cur_page

                tmp_result = self.http_post(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id), params=params,
                    method='post')
                search_result['list'] += tmp_result['list']

        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params=None):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    print r.content
                    return json.loads(r.content)
            except Exception as e:
                print e
                return {"list": []}

        elif method in ("info_port",):
            # 这里是交换机端口关联，因为关联成功返回的信息{u'message': u'', u'code': 0, u'data': None, u'error': u''}， 如果像上面那么写 data返回的是None
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if data.get('code') == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


class ThreadInsert(object):
    def __init__(self):
        self.inserdata = {}
        start_time = time.time()
        self.data = self.getData()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        st = time.time()
        self.easyopsObj = EasyopsPubic()
        data = self.easyopsObj()
        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data[i:i + n] for i in range(0, len(data), n)]
        if len(result) > n:
            self.pool = Pool(40)
        else:
            self.pool = Pool(len(result))

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for i in content:
            res.append(self.pool.spawn(self.gevent_data, i))
        gevent.joinall(res)

        for k, v in self.inserdata.items():
            data = {
                "keys": ['name', ],
                "datas": v
            }
            # info_url = "/object/{0}/instance/_import".format(INSERDATAMODEL)
            # if len(data['datas']):
            #     self.easyopsObj.http_post('many_post', info_url, data)

    def gevent_data(self, i):
        if not i.get('code', ''):
            instanceId = i.get('instanceId') # 服务节点的实例ID
            configInfo = i.get('configInfo', [])  # 配置信息 list
            agentIp = i.get('agentIp', '')  # 主机IP
            ip = i.get('ip', '')  # 监听IP
            port = i.get('port', '')  # 监听端口
            type = i.get('type', '')  # 节点类型
            if i.get('HOST_IP'):
                host_instanceId = i.get('HOST_IP')[0].get('instanceId')
            else:
                host_instanceId = ''

            listeners = ''
            pid_file = ''
            log_error = ''
            basedir = ''
            datadir = ''
            version = ''
            if configInfo:
                for info in configInfo:
                    key = info.get('key', '')
                    if key == 'listeners':
                        listeners = info.get('value', '')

                    if key == 'pid_file':
                        pid_file = info.get('value', '')

                    if key == 'log_error':
                        log_error = info.get('value', '')

                    if key == 'basedir':
                        basedir = info.get('value', '')

                    if key == 'datadir':
                        datadir = info.get('value', '')

                    if key == 'version':
                        version = info.get('value', '')
            # 筛选监听IP类型
            if all([instanceId, agentIp, ip, port, type]):
                # 1. 判断mysql 监听IP为 [[::], 0.0.0.0 当前IP]
                if ip in ['[::]', '0.0.0.0', agentIp] or (ip == '::'):
                    data = {
                        "name": agentIp + "_" + type + '_' + str(port),
                        "agentIp": agentIp,
                        "ip": ip,
                        "port": str(port),
                        "type": type,
                        # 配置信息
                        "listeners": listeners,
                        "pid_file": pid_file,
                        'log_error': log_error,
                        "basedir": basedir,
                        "datadir": datadir,
                        "version": version,
                        'host_instanceId': host_instanceId

                    }
                    instanbcedKey = agentIp + "-" +host_instanceId
                    if not self.inserdata.has_key(instanbcedKey):
                        self.inserdata[instanbcedKey] = []
                    self.inserdata[instanbcedKey].append(data)

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
    ThreadInsert()
