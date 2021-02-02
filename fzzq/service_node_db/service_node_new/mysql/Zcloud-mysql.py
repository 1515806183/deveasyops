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
import random

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


class Synchronize():
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getNodeInfo(self):
        """
        获取 平台当前实例信息，保存ip，ip和实例ID
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=SERVICE_MODEL)
        params = {
            "fields": {'name': True, "HOST.use": True, "HOST.sn": True, "USER.name": True,
                       "USER.nickname": True}}
        dataList = http_post('POSTS', url, params)

        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE=SERVICE_MODEL))

        return dataList

    def getData(self):
        st = time.time()
        # 获取现网服务数据
        self.dataList = self.getNodeInfo()

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def gevent_data(self, data):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        # 判断name是否在服务节点里面，如果在的话就pass， 不在新建实例
        NodeName = str(data.get('name'))
        HostData = data.get('HOST')
        UserData = data.get('USER')
        ip, port = NodeName.split(":")

        # 处理主机信息
        host_list = []
        if HostData:
            for host in HostData:
                sn = host.get('sn', '')
                use = host.get('use', '')
                host_list.append({
                    "ip": ip,
                    "sn": sn,
                    "use": use
                })
        else:
            host_list.append({
                "ip": ip,
                "sn": "",
                "use": ""
            })

        # 处理用户信息
        user_list = []
        if UserData:
            for user in UserData:
                name = user.get('name', '')
                nickname = user.get('nickname', '')
                user_list.append({
                    "name": name,
                    "nickname": nickname
                })
        else:
            user_list.append({
                "name": "",
                "nickname": ""
            })

        _SERVICENODE = [{
            "agentIp": ip,
            "port": int(port),
            "type": node_type
        }]

        data = {
            "jsonStr": {
                "list": [
                    {
                        "HOST": host_list,
                        "USER": user_list,
                        "_SERVICENODE": _SERVICENODE
                    }
                ]
            }
        }

        try:
            # 随机停顿下
            num = random.random()
            time.sleep(num)

            url = "http://28.163.1.183:8023/dbaasInfrastructure/cmdbAttr/dataParser"
            headers = {
                'token': 'e7043641-4bcc-368e-9b09-3dbe894cd24f',
                'Content-Type': 'application/json'
            }
            response = requests.request("POST", url, headers=headers, json=json.dumps(data), timeout=20)
            data = response.text.encode('utf8')
            data = json.loads(data)
            service_node = json.loads(data.get('data')).get('list')[0].get('_SERVICENODE')[0]
            zcloud_instance_id = service_node.get('zcloud_instance_id')
            if zcloud_instance_id:
                service_node['name'] = NodeName
                service_node['existence'] = u"是"
                # 处理类型
                zcloud_cluster_type = service_node.get('zcloud_cluster_type')
                if not isinstance(zcloud_cluster_type, unicode):
                    if zcloud_cluster_type == 1:
                        service_node['zcloud_cluster_type'] = u"单实例"
                    elif zcloud_cluster_type == 2:
                        service_node['zcloud_cluster_type'] = u"主从"

                # 处理是否是集群
                zcloud_is_cluster = service_node.get('zcloud_is_cluster', 0)
                if zcloud_is_cluster:
                    service_node['zcloud_is_cluster'] = u"是"
                else:
                    service_node['zcloud_is_cluster'] = u"否"

                # 处理是否开发binlog
                zcloud_is_open_binlog = service_node.get('zcloud_is_open_binlog', 0)
                if zcloud_is_open_binlog:
                    service_node['zcloud_is_open_binlog'] = u"是"
                else:
                    service_node['zcloud_is_open_binlog'] = u"否"

                return service_node

            else:
                return {
                    "name": NodeName,
                    "existence": u"否"
                }

        except Exception as e:
            logging.error("Instance data, failed to get data, instance name: %s, error: %s" % (NodeName, e))

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
    Synchronize()
