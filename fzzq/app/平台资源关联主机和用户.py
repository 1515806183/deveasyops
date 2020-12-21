# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading, logging, sys
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

# create logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create a file handler
logger_handler = logging.StreamHandler(stream=sys.stdout)
logger_handler.setLevel(logging.DEBUG)

# create a logging format
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(lineno)d] %(message)s', '%Y-%m-%d %H:%M:%S')
logger_handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(logger_handler)

monkey.patch_all()

# CMDB配置
easyops_cmdb_host = '192.168.110.170'
easyops_org = '1033'
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 插入数据模型ID
modelID = 'tuxedoltwo'

if modelID == "MYSQL_SERVICE":
    nodeID = 'mysql'
elif modelID == 'MONGODB_SERVICE':
    nodeID = 'mongodb'
elif modelID == 'ELASTICSEARCH_SERVICE':
    nodeID = 'elasticsearch'
elif modelID == 'ORACLE_SERVICE':
    nodeID = 'oracle'
elif modelID == 'SQLSERVICE':
    nodeID = 'sqlserver'
elif modelID == 'NGINX_SERVICE':
    nodeID = 'nginx'
elif modelID == 'TOMCAT_SERVICE':
    nodeID = 'tomcat'
elif modelID == 'WEBLOGIC_SERVICE':
    nodeID = 'weblogic'
elif modelID == 'KAFKA_SERVICE':
    nodeID = 'kafka'
elif modelID == 'RABBITMQ_SERVICE':
    nodeID = 'rabbitmq'
elif modelID == 'REDIS_SERVICE':
    nodeID = 'redis'
elif modelID == 'MEMCACHED_SERVICE':
    nodeID = 'memcached'
elif modelID == 'ZOOPKEEPER_SERVICE':
    nodeID = 'zookeeper'
elif modelID == "JBOSS_SERVER":
    nodeID = 'java'
    mq_name = 'flink_tracing'

elif modelID == "tuxedolone":
    nodeID = 'CTBase.exe'
    mq_name = 'CTBase.exe'

elif modelID == "tuxedoltwo":
    nodeID = 'tomcat'
    mq_name = 'YNRCB_B2EF'

else:
    nodeID = ''

# 携程池
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)


class EasyopsPubic(object):

    def searchQueryData(self):
        """
        通过查询参数查询数据
        :return: 
        """

        if modelID == 'HOST':
            ConfigParams = {"query": {}, "fields": {"instanceId": True, "APP": True, "ip": True},
                            "only_relation_view": True,
                            "only_my_instance": False}

        elif modelID == "JBOSS_SERVER":
            ConfigParams = {"query": {
                "$and": [{"$or": [{"type": {"$eq": nodeID}}]},
                         {"$or": [{"provider.cwd": {"$like": "%" + mq_name + "%"}}]}]},
                "fields": {"instanceId": True, "agentIp": True, "type": True, "provider": True},
                "only_relation_view": True, "only_my_instance": False}

        elif modelID == "tuxedolone":
            ConfigParams = {"query": {
                "$and": [{"$or": [{"type": {"$eq": nodeID}}]},
                         {"$or": [{"provider.cmd": {"$like": "%" + mq_name + "%"}},
                                  ]}]},
                "fields": {"instanceId": True, "agentIp": True, "type": True, "provider": True},
                "only_relation_view": True, "only_my_instance": False}
        elif modelID == "tuxedoltwo":
            ConfigParams = {"query": {
                "$and": [{"$or": [{"type": {"$eq": 'TOMCAT_SERVICE'}}]},
                         {"$or": [{"provider.cmd": {"$like": "%" + mq_name + "%"}},
                                  ]}]},
                "fields": {"instanceId": True, "agentIp": True, "type": True, "provider": True},
                "only_relation_view": True, "only_my_instance": False}
        else:
            ConfigParams = {"query": {"$and": [{"$or": [{"type": {"$eq": nodeID}}]}]},
                            "fields": {"instanceId": True, "agentIp": True}, "only_relation_view": True,
                            "only_my_instance": False}

        return self.instance_search("_SERVICENODE", ConfigParams)

    # 搜索实例
    def instance_search(self, object_id, params):
        """
        :param object_id: 模型ID
        :param params: 查询条件
        :return:
        """
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params={}):
        page_size = 100
        if not params.has_key('page_size'):
            params['page_size'] = page_size

        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)

        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    total_instance_nums = int(ret['total'])  # 1252
                    if total_instance_nums > page_size:
                        pages = total_instance_nums / page_size  # total pages = pages + 2
                        for cur_page in range(2, pages + 2):
                            params['page'] = cur_page
                            temp_ret = self.http_post(
                                restful_api=restful_api,
                                params=params,
                                method='post_page')
                            ret['list'] += temp_ret['list']
                    return ret
            except Exception as e:
                return {"list": []}

        # post翻页查询，依赖http_post
        elif method in ('post_page',):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers, timeout=60)
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    total_instance_nums = int(ret['total'])  # 1252

                    if total_instance_nums > page_size:
                        pages = total_instance_nums / page_size  # total pages = pages + 2
                        for cur_page in range(2, pages + 2):
                            params['page'] = cur_page
                            tmp_result = self.http_post(
                                restful_api=restful_api,
                                params=params,
                                method='get_page')
                            ret['list'] += tmp_result['list']
                    return ret
            except Exception as e:
                return {"list": []}

        # get翻页查询，依赖http_post
        elif method in ('get_page',):
            try:
                r = requests.get(url, headers=headers, timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        # PUT
        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)['code']
            except Exception as e:
                return {"list": []}

        # 批量插入
        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)
            except Exception as e:
                print e
                return {"list": []}

        elif method in ("info_port",):
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

        elif method in ("info_set",):
            # 会对比关系是否存在, 多余的关系移除掉，不存在的关系添加上
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if int(data.get('code')) == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False

        # 删除
        elif method in ('DELETE', 'delete'):
            try:
                r = requests.delete(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if int(data.get('code')) == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


# 平台服务自动创建实例
class ThreadInsert(EasyopsPubic):
    def __init__(self):
        self.ip_name_list = self.getnodeapp()  # 获取平台服务当前有哪些列表
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        self.delete_node()  # 清理数据
        print("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def _gethostinstanceId(self):
        """
        服务节点现网数据
        :return:
        """
        ip_list = set()
        server_ip_data = self.searchQueryData()
        for data in server_ip_data:
            ip_list.add(data.get('agentIp'))
        return list(ip_list)

    def getnodeapp(self):
        """
        获取 平台当前实例信息，保存ip，ip和实例ID
        :return:
        """
        self.all_node_list = {}  # 平台数据，清理数据要用

        restful_api = '/object/%s/instance/_search' % modelID
        params = {"fields": {'name': True}}

        dataList = self.http_post('post', restful_api, params)

        node_list = []
        try:
            # name 为key， instanceId为v
            for data in dataList['list']:
                ip_name = data.get('name')
                instanceId = data.get('instanceId')
                node_list.append(ip_name)
                self.all_node_list.update({ip_name: instanceId})
        except Exception as e:
            node_list = []
        return node_list

    def getData(self):
        st = time.time()
        # 获取oracle数据
        self.dataList = self._gethostinstanceId()

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(modelID)
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, ip):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        # 判断IP是否在服务节点里面，如果在的话就pass， 不在新建实例
        if ip not in self.ip_name_list:
            return {"name": str(ip)}

    def delete_node(self):
        # 删除多余的实例
        get_easyops_node_data = self.getnodeapp()  # 获取平台当前实例信息

        delete_list = list(set(get_easyops_node_data) - set(self.dataList))  # 平台数据 - 减去现网数据，剩下的就是要删除的数据

        arges = ""
        for data in delete_list:
            instanceId = self.all_node_list.get(data) + ';'
            arges += instanceId

        delete_url = "/object/{}/instance/_batch".format(modelID) + "?instanceIds=" + arges
        res = self.http_post('delete', delete_url)

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


# 自动增加节点发现功能
class AutoAddNode(EasyopsPubic):
    def __init__(self):
        self.data = self.getData()
        self.task()

    def getnodeapp(self):
        """
        获取平台资源实例
        :return:
        """
        restful_api = '/object/%s/instance/_search' % modelID
        params = {"fields": {'name': True}}
        dataList = self.http_post('post', restful_api, params)

        node_list = []
        # name 为key， instanceId为v
        for data in dataList['list']:
            instanceId = data.get('instanceId')
            ip_name = data.get('name')
            node_list.append({ip_name: instanceId})
        return node_list

    def getData(self):
        st = time.time()
        dataList = self.getnodeapp()  # 获取平台数据

        result = [dataList[i:i + n] for i in range(0, len(dataList), n)]

        print("获取平台资源实例，共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):

        res = []
        for data in content:
            res.append(pool.spawn(self.gevent_data, data))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(modelID)
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, data):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        for k, v in data.items():
            if modelID == "JBOSS_SERVER":
                data = {"featurePriority": "500", "featureEnabled": "true",
                        "featureRule": [{"key": "agentIp", "method": "eq", "value": k, "label": "AgentIp"},
                                        {"key": "provider.cwd", "method": "like", "value": mq_name, "label": "工作目录"}]}
            elif modelID == "tuxedolone":
                data = {"featurePriority": "500", "featureEnabled": "true",
                        "featureRule": [{"key": "agentIp", "method": "eq", "value": k, "label": "AgentIp"},
                                        {"key": "provider.cmd", "method": "like", "value": mq_name, "label": "启动命令"}]}
            else:
                data = {"featurePriority": "500", "featureEnabled": "true",
                        "featureRule": [{"key": "agentIp", "method": "eq", "value": k, "label": "AgentIp"}]}

            data.update({"name": k})
        return data

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


# 增加实例主机和运维人员关系
class AutoADDRela(EasyopsPubic):
    def __init__(self):
        self.AllHost = self.GetAllHost()  # 获取所有主机信息

        self.data = self.getData()  # 获取所有的主机
        self.task()

    def GetAllHost(self):
        restful_api = '/object/%s/instance/_search' % 'HOST'
        params = {"query": {}, "fields": {"instanceId": True, "ip": True, "owner.instanceId": True}}
        dataList = self.http_post('post', restful_api, params)

        dataDict = {}
        # name 为key， instanceId为v
        for data in dataList['list']:
            instanceId = data.get('instanceId')
            ip_name = data.get('ip')
            owner = data.get('owner')
            if not dataDict.has_key(ip_name):
                dataDict.update({ip_name: {"instanceId": instanceId, "owner": owner}})

        return dataDict

    def getnodeapp(self):
        """
        获取平台资源实例
        :return:
        """
        restful_api = '/object/%s/instance/_search' % modelID
        params = {"query": {}, "fields": {"name": True}}
        dataList = self.http_post('post', restful_api, params)

        node_list = []
        # name 为key， instanceId为v
        for data in dataList['list']:
            name = data.get('name')
            node_list.append(name)

        return node_list

    def getData(self):
        st = time.time()
        dataList = self.getnodeapp()  # 获取平台数据

        result = [dataList[i:i + n] for i in range(0, len(dataList), n)]

        print("获取主机信息，共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):

        res = []
        for data in content:
            res.append(pool.spawn(self.gevent_data, data))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(modelID)
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, data):
        """
        :param data: 每条实例名
        :return:
        """
        if self.AllHost.has_key(data):
            info = self.AllHost.get(data)
            owner_list = info.get('owner')
            try:
                hostInstanceId = [info.get('instanceId')]
            except Exception as e:
                hostInstanceId = []
            owner = [user.get('instanceId') for user in owner_list if user]
            res = {
                "name": data,
                "HOST": hostInstanceId,
                "USER": owner
            }

            return res

    # 开启多线程任务
    def task(self):
        # 设定最大队列数和线程数
        q = Queue(maxsize=20)
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


# 实例配置信息同步
class AutoAddConfig(EasyopsPubic):
    pass


def run():
    # 添加服务节点到实例
    ThreadInsert()
    # 增加实例的自动发现
    AutoAddNode()
    # 增加实例主机和运维人员关系
    AutoADDRela()


if __name__ == '__main__':
    run()
