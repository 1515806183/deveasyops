# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

# CMDB配置
easyops_cmdb_host = '18.100.254.232'
easyops_org = '3087'
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 插入数据模型ID
INSERDATAMODEL = name

if INSERDATAMODEL == "MYSQL_SERVICE":
    eq_data = 'mysql'
elif INSERDATAMODEL == 'MONGODB_SERVICE':
    eq_data = 'mongodb'
elif INSERDATAMODEL == 'ELASTICSEARCH_SERVICE':
    eq_data = 'elasticsearch'
elif INSERDATAMODEL == 'ORACLE_SERVICE':
    eq_data = 'oracle'
elif INSERDATAMODEL == 'SQLSERVICE':
    eq_data = 'sqlserver'
elif INSERDATAMODEL == 'NGINX_SERVICE':
    eq_data = 'nginx'
elif INSERDATAMODEL == 'TOMCAT_SERVICE':
    eq_data = 'tomcat'
elif INSERDATAMODEL == 'WEBLOGIC_SERVICE':
    eq_data = 'weblogic'
elif INSERDATAMODEL == 'KAFKA_SERVICE':
    eq_data = 'kafka'
elif INSERDATAMODEL == 'RABBITMQ_SERVICE':
    eq_data = 'rabbitmq'
elif INSERDATAMODEL == 'REDIS_SERVICE':
    eq_data = 'redis'
elif INSERDATAMODEL == 'MEMCACHED_SERVICE':
    eq_data = 'memcached'
elif INSERDATAMODEL == 'ZOOPKEEPER_SERVICE':
    eq_data = 'zookeeper'
elif INSERDATAMODEL == "RocketMQ_SERVICE":
    eq_data = 'java'
    mq_name = 'rocketmq'
else:
    eq_data = ''


# Easyops查询实例
class EasyopsPubic(object):

    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        if INSERDATAMODEL == 'HOST':
            # 搜索实列列表条件
            ConfigParams = {"query": {}, "fields": {"instanceId": True, "APP": True, "ip": True},
                            "only_relation_view": True,
                            "only_my_instance": False}

        elif INSERDATAMODEL == "RocketMQ_SERVICE":
            # 搜索实列列表条件
            ConfigParams = {"query": {
                "$and": [{"$or": [{"type": {"$eq": eq_data}}]},
                         {"$or": [{"provider.cwd": {"$like": "%" + mq_name + "%"}}]}]},
                "fields": {"instanceId": True, "agentIp": True, "type": True, "provider": True},
                "only_relation_view": True, "only_my_instance": False}
        else:
            # 搜索实列列表条件
            ConfigParams = {"query": {"$and": [{"$or": [{"type": {"$eq": eq_data}}]}]},
                            "fields": {"instanceId": True, "agentIp": True}, "only_relation_view": True,
                            "only_my_instance": False}

        return self.instance_search("_SERVICENODE", ConfigParams)

    # 搜索实例
    def instance_search(self, object_id, params):
        """
        :param object_id: 配置文件中的搜索模型ID
        :param params: 配置文件中的搜索查询条件
        :return:
        """
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params={}):
        if not params.has_key('page_size'):
            page_size = 300
            params['page_size'] = page_size

        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)

        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
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

        elif method in ('post_page',):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers)
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
                                method='page')
                            ret['list'] += tmp_result['list']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['code']
            except Exception as e:
                return {"list": []}

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
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

        elif method in ("info_set",):
            # 会对比关系是否存在, 多余的关系移除掉，不存在的关系添加上
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if int(data.get('code')) == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False

        elif method in ('DELETE', 'delete'):
            try:
                r = requests.delete(url, headers=headers, data=json.dumps(params))
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
        self.all_node_list = {}  # 平台mq节点实例，ip:实例ID
        self.ip_name_list = self.getnodeapp()  # 获取平台服务当前有哪些列表
        start_time = time.time()
        self.data = self.getData()
        self.task()
        # self.delete_node()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def _gethostinstanceId(self):
        """
        服务节点现网数据
        :return:
        """
        ip_list = set()
        server_ip_data = self.search_auto_collect_switch()
        for data in server_ip_data:
            ip_list.add(data.get('agentIp'))
        return list(ip_list)

    def getnodeapp(self):
        """
        获取 平台当前实例信息，保存ip，ip和实例ID
        :return:
        """
        restful_api = '/object/%s/instance/_search' % INSERDATAMODEL
        params = {"fields": {'name': True}}

        dataList = self.http_post('post', restful_api, params, INSERDATAMODEL)

        node_list = []
        # name 为key， instanceId为v
        for data in dataList['list']:
            ip_name = data.get('name')
            instanceId = data.get('instanceId')
            node_list.append(ip_name)
            self.all_node_list.update({ip_name: instanceId})
        return node_list

    def getData(self):
        st = time.time()
        # 获取oracle数据
        self.dataList = self._gethostinstanceId()

        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]
        if len(result) > n:
            self.pool = Pool(40)
        else:
            self.pool = Pool(len(result))

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(self.pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(INSERDATAMODEL)
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)

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

        delete_url = "/object/{}/instance/_batch".format(INSERDATAMODEL) + "?instanceIds=" + arges
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
class auto_add_node(EasyopsPubic):
    def __init__(self):
        self.data = self.getData()
        self.task()

    def getnodeapp(self):
        """
        获取 服务的 ip 和 instanceId 为后面建立关系
        :return:
        """
        restful_api = '/object/%s/instance/_search' % INSERDATAMODEL
        params = {"fields": {'name': True}}
        dataList = self.http_post('post', restful_api, params, INSERDATAMODEL)

        node_list = []
        # name 为key， instanceId为v
        for data in dataList['list']:
            instanceId = data.get('instanceId')
            ip_name = data.get('name')
            node_list.append({ip_name: instanceId})
        return node_list

    def getData(self):
        st = time.time()
        # 获取oracle数据
        dataList = self.getnodeapp()

        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [dataList[i:i + n] for i in range(0, len(dataList), n)]
        if len(result) > n:
            self.pool = Pool(40)
        else:
            self.pool = Pool(len(result))

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):

        res = []
        for data in content:
            res.append(self.pool.spawn(self.gevent_data, data))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(INSERDATAMODEL)
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, data):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        for k, v in data.items():
            if INSERDATAMODEL == "RocketMQ_SERVICE":
                data = {"featurePriority": "500", "featureEnabled": "true",
                        "featureRule": [{"key": "agentIp", "method": "eq", "value": k, "label": "AgentIp"},
                                        {"key": "provider.cwd", "method": "like", "value": mq_name, "label": "工作目录"}]}
            else:
                data = {"featurePriority": "500", "featureEnabled": "true",
                        "featureRule": [{"key": "agentIp", "method": "eq", "value": k, "label": "AgentIp"}]}

            data.update({"name": k})
        return data

        # res = self.easyopsObj.http_post('put', url, data)
        # if int(res) == 0:
        #     print '%s 添加自动发现规则成功' % str(k)

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
    # 添加服务节点到实例
    ThreadInsert()
    # 增加实例的自动发现
    auto_add_node()
