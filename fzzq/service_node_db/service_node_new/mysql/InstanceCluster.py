# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: InstanceCluster.py
@time: 2021/1/27 11:35
@desc:实例集群
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
class InstanceCluster():
    def __init__(self):
        self.LatestDataList = []  # 加入cmdb的最新数据
        self.AddedData = []  # 保存已经处理后的实例数据，包括关系数据 ip:port
        # self.node_inf 存的是name(IP:prot) 和实例ID
        # cluster_true_list 存的是集群的数据
        # cluster_false_list 存的是单列数据
        self.node_info, cluster_true_list, cluster_false_list = self.getNodeInfo()  # 获取服务对应的服务节点列表（平台内的数据）
        start_time = time.time()
        self.data = self.getData(cluster_true_list)
        self.task()
        self.SingleColumn(cluster_false_list)  # 处理单例数据
        self.delete_node()  # 删除多余的集群信息
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getNodeInfo(self):
        """
        获取平台服务实例数据
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=SERVICE_MODEL)
        params = {"fields": {'name': True, "memo": True, "zcloud_relation_node": True, "agentIp": True, "port": True,
                             "existence": True, "zcloud_is_cluster": True}}
        dataList = http_post('POSTS', url, params)
        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE=SERVICE_MODEL))

        cluster_false_list = []  # 不是集群的实例列表
        cluster_true_list = []  # 是集群的的实例列表
        node_info = {}  # 保存实例数据，以ip:端口为k， 实例ID为V
        for data in dataList:
            # zcloud 纳管的数据，这里区分实例是否是集群
            if data.get('existence') == "是":
                # 是集群实例
                if data.get('zcloud_is_cluster') == "是":
                    cluster_true_list.append(data)
                    node_instanceId = data.get('instanceId')
                    node_name = str(data.get('name'))
                    node_info.update({
                        node_name: node_instanceId
                    })
                # 不是集群的实例
                else:
                    cluster_false_list.append(data)

        logging.info(
            'cluster_true_list len: %s, cluster_false_list len: %s' % (len(cluster_true_list), len(cluster_false_list)))
        return node_info, cluster_true_list, cluster_false_list

    def _getCurrentNetwork(self):
        """
        获取平台集群数据
        :return:
        """
        params = {"fields": {"name": True}}
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="MYSQL")

        ClusterList = http_post('POSTS', url, params)
        logging.info('Number of cluster instances: %s' % len(ClusterList))
        if not ClusterList: return []

        # 将集群信息保存为list，name,后续清理数据用
        diff_list = {}
        for cluster in ClusterList:
            diff_list.update({cluster.get('name'): cluster.get('instanceId')})  # {ip:prot}
        return diff_list

    def getData(self, data):
        st = time.time()
        result = [data[i:i + n] for i in range(0, len(data), n)]
        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def gevent_data(self, data):
        """
        :param i:  每条服务实例数据
        :return:
        """
        node_instanceId = data.get('instanceId')
        node_name = data.get('name')
        if node_name in self.AddedData:
            return

        # 辅助变量数据
        cluster_need_node_instanceId = []  # 集群关联实例关系ID
        cluster_need_node_ip_port_name = []  # 加入集群的name

        # 将实例放进已经处理好的集合中
        cluster_need_node_instanceId.append(node_instanceId)
        self.AddedData.append(node_name)

        # 实例关系数据
        relation_node = data.get('zcloud_relation_node')
        for relation in relation_node:
            relation_ip = relation.get('ip')
            relation_port = str(relation.get('port'))
            relation_node_name = relation_ip + ":" + relation_port
            # 判断关系ip是否处理过
            if relation_node_name not in self.AddedData:
                self.AddedData.append(relation_node_name)
                # 从现网集合获取对应的实例ID信息，通过ip:port 获取
                relation_node_instanceId = self.node_info.get(relation_node_name)
                cluster_need_node_instanceId.append(relation_node_instanceId)
                cluster_need_node_ip_port_name.append(relation_node_name)

        cluster_need_node_ip_port_name.append(node_name)

        name = "-".join(sorted(cluster_need_node_ip_port_name))
        # 把加入的数据放进集合内
        self.LatestDataList.append(name)
        return {"name": name,
                "MYSQL_SERVICE": cluster_need_node_instanceId}

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
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID="MYSQL")
            time.sleep(1)
            res = http_post('repo', url, data)
            logging.info('cluster_true_list Return of inserted data: %s' % res)
        else:
            logging.info('cluster_true_list There is no data to insert')

    # 处理单例数据
    def SingleColumn(self, cluster_false_list):
        if not cluster_false_list:
            return
        inserrt_list = []
        for cluster in cluster_false_list:
            name = cluster.get('name')
            instanceId = cluster.get('instanceId')
            inserrt_list.append({
                "name": name,
                "MYSQL_SERVICE": [instanceId, ]
            })
            self.LatestDataList.append(name)

        data = {
            "keys": ['name'],
            "datas": inserrt_list
        }

        if len(data['datas']):
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID="MYSQL")
            time.sleep(1)
            res = http_post('repo', url, data)
            logging.info('cluster_false_list Return of inserted data: %s' % res)
        else:
            logging.info('cluster_false_list There is no data to insert')

    def delete_node(self):
        CurrentNetwork = self._getCurrentNetwork()  # 现网集群数据 ip-ip：端口，供后续清理数据用
        arges = []
        for info in CurrentNetwork:
            if info not in self.LatestDataList:
                remove_id = CurrentNetwork[info]
                arges.append(remove_id)

        logging.info('Number of cluster instances deleted: %s' % len(arges))
        if arges:
            delete_url = "http://{HOST}/object/{ID}/instance/_batch".format(HOST=cmdb_host,
                                                                            ID="MYSQL") + "?instanceIds=" + ";".join(
                arges)
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


if __name__ == '__main__':
    InstanceCluster()
