# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: service_node.py
@time: 2021/1/26 12:17
@desc:
'''
import time, requests, json, subprocess, re
import threading, logging, sys
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

reload(sys)
sys.setdefaultencoding('utf8')
monkey.patch_all()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# 携程池
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

cmdb_host = "28.163.0.123"
easyops_org = "3087"

cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}

SERVICE_MODEL = "MYSQL_SERVICE"
node_type = "mysql"


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
                return data
            else:
                return r.content
        except Exception as e:
            return e


# 自动发现服务节点实例，以auto_IP:端口为name
class AutoDiscoveryInstance():
    def __init__(self):
        self.node_list, self.all_node_dict = self.getNodeInfo()  # 获取服务对应的服务节点列表（平台内的数据）
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        self.delete_node()  # 清理数据
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getNodeInfo(self):
        """
        获取 平台当前实例信息，保存ip，ip和实例ID
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=SERVICE_MODEL)
        params = {"fields": {'name': True}}
        dataList = http_post('POSTS', url, params)
        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE=SERVICE_MODEL))

        node_list = []
        all_node_dict = {}
        try:
            # name 为key， instanceId为v
            for data in dataList:
                name = data.get('name')
                instanceId = data.get('instanceId')
                node_list.append(name)
                if not all_node_dict.has_key(name):
                    all_node_dict.update({name: instanceId})
        except Exception as e:
            node_list = []
        logging.info('len instance :%s' % str(len(node_list)))
        return node_list, all_node_dict

    def _getinstanceId(self):
        """
        服务节点现网数据
        :return:
        """
        need_insert_list = []
        params = {"query": {"$and": [{"$or": [{"type": {"$eq": node_type}}]}]},
                  "fields": {"instanceId": True, "agentIp": True, "port": True}, "only_relation_view": True,
                  "only_my_instance": False}
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="_SERVICENODE")

        NodeList = http_post('POSTS', url, params)
        logging.info('Number of data service nodes in current network: %s' % len(NodeList))

        # 判断数据是否有端口
        for node in NodeList:
            if node.has_key('port'):
                need_insert_name = node.get('agentIp') + ":" + str(node.get('port'))
                if need_insert_name not in need_insert_list:
                    need_insert_list.append(need_insert_name)
        logging.info('Number of service nodes after cleaning: %s' % len(list(set(need_insert_list))))
        return list(set(need_insert_list))

    def getData(self):
        st = time.time()
        # 获取现网服务数据
        self.dataList = self._getinstanceId()

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def gevent_data(self, name):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        # 判断name是否在服务节点里面，如果在的话就pass， 不在新建实例
        if name not in self.node_list:
            return {"name": name}

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
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID=SERVICE_MODEL)
            time.sleep(1)
            res = http_post('repo', url, data)
            logging.info('Return of inserted data: %s' % res)
        else:
            logging.info('There is no data to insert')

    def delete_node(self):
        # 删除多余的实例
        node_list, node_name_id_dict = self.getNodeInfo()  # 获取平台当前实例信息

        delete_list = list(set(node_list) - set(self.dataList))  # 平台数据 - 减去现网数据，剩下的就是要删除的数据

        arges = ""
        for data in delete_list:
            instanceId = node_name_id_dict.get(data) + ';'
            arges += instanceId

        if arges:
            delete_url = "http://{HOST}/object/{ID}/instance/_batch".format(HOST=cmdb_host,
                                                                            ID=SERVICE_MODEL) + "?instanceIds=" + arges
            res = http_post('DELETE', delete_url)
            logging.info('The deleted data is :%s' % res)

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


# 关联主机和运维人员信息
class AutoADDRela():
    def __init__(self):
        start_time = time.time()
        logging.info('Start to get the host, personnel information')
        self.data = self.getData()  # 获取所有平台服务信息
        self.task()
        logging.info("========= 增加更新主机用户数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getnodeapp(self):
        """
        获取平台资源实例
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=SERVICE_MODEL)
        params = {"query": {}, "fields": {"name": True}}
        dataList = http_post('POSTS', url, params)
        logging.info('The number of service instances obtained is: %s' % len(dataList))

        return dataList

    def getData(self):
        st = time.time()
        dataList = self.getnodeapp()  # 获取平台数据
        result = [dataList[i:i + n] for i in range(0, len(dataList), n)]
        logging.info("获取主机信息，共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
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
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID=SERVICE_MODEL)
            time.sleep(1)
            res = http_post('repo', url, data)
            logging.info('Return of inserted data: %s' % res)
        else:
            logging.info('There is no data to insert')

    def gevent_data(self, data):
        """
        :param data: 每条实例名
        :return:
        """
        node_name = data.get('name')  # 服务实例name
        ip, port = node_name.split(":")
        # 通过IP查询对应的主机信息
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="HOST")
        params = {"query": {"ip": {"$eq": ip}}, "fields": {"instanceId": True, "ip": True,
                                                           "owner.instanceId": True, "sn": True, "use": True}}
        HostData = http_post('POSTS', url, params)

        USER = []
        HOST = []
        data = {"name": node_name}
        if HostData:
            HostData = HostData[0]
            HostInstanceId = HostData.get('instanceId')
            HOST.append(HostInstanceId)
            ownerList = HostData.get('owner')
            if ownerList:
                for user in ownerList:
                    userInstanceId = user.get('instanceId')
                    USER.append(userInstanceId)

            data.update({
                "USER": USER,
                "HOST": HOST,
                "sn": HostData.get('sn'),
                "use": HostData.get('use'),
            })
        # 增加服务节点
        data.update({"featurePriority": "500", "featureEnabled": "true",
                     "featureRule": [{"key": "agentIp", "method": "eq", "value": ip, "label": "AgentIp"},
                                     {"key": "port", "method": "eq", "value": port, "label": "监听端口"}]})

        return data

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


if __name__ == '__main__':
    AutoDiscoveryInstance()
    AutoADDRela()
