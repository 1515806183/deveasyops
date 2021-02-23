# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: service_node.py
@time: 2021/1/26 12:17
@desc: db应用，根据服务端口来上报数据到zcloud
'''
import time, requests, json, subprocess, re
import threading, logging, sys, copy
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool
import pprint

reload(sys)
sys.setdefaultencoding('utf8')
monkey.patch_all()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# 携程池
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

cmdb_host = "10.163.128.232"
# cmdb_host = "28.163.0.123"
easyops_org = "3087"
db_app_name = ''

cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}

http_zcloud_url = {
    "test": "http://{HOST}:8023/dbaasInfrastructure/cmdbAttr/dataParser".format(HOST="100.116.9.144"),
    # "test": "http://{HOST}:8023/dbaasInfrastructure/cmdbAttr/dataParser".format(HOST="28.163.1.183"),
    "pro": "http://{HOST}:8023/dbaasInfrastructure/cmdbAttr/dataParser".format(HOST="10.163.128.19"),
}
zcloud_headers = {
    "test": {
        'token': 'e7043641-4bcc-368e-9b09-3dbe894cd24f',
        'Content-Type': 'application/json'
    },
    "pro": {
        'token': 'e7043641-4bcc-368e-9b09-3dbe894cd24f',
        'Content-Type': 'application/json'
    }
}


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


class InstanceCluster():
    def __init__(self, SERARCHMODEL, REPOMODEL):
        self.SERARCHMODEL = SERARCHMODEL
        self.REPOMODEL = REPOMODEL
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
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=self.SERARCHMODEL)
        params = {"fields": {'name': True, "memo": True, "zcloud_relation_node": True, "agentIp": True, "port": True,
                             "existence": True, "zcloud_is_cluster": True, "zcloud_cluster_type": True}}
        dataList = http_post('POSTS', url, params)
        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE=self.SERARCHMODEL))

        cluster_false_list = []  # 不是集群的实例列表
        cluster_true_list = []  # 是集群的的实例列表
        node_info = {}  # 保存实例数据，以ip:端口为k， 实例ID为V
        for data in dataList:
            # zcloud 纳管的数据，这里区分实例是否是集群
            if data.get('existence') == "是":
                # 是集群实例
                if str(data.get('zcloud_cluster_type')) == u"主从":
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
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID=self.REPOMODEL)

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
        if not relation_node:
            logging.warning('node_name: %s No related node information' % node_name)
            return
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
                self.SERARCHMODEL: cluster_need_node_instanceId}

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
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID=self.REPOMODEL)
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
                self.SERARCHMODEL: [instanceId, ]
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
                                                                            ID=self.REPOMODEL) + "?instanceIds=" + ";".join(
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


# 从应用出发，获取服务节点，获取zclou数据
class AutoAppServiceNode():
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getAppNodeInfo(self):
        """
        获取 应用信息,服务节点信息，主机信息
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="APP")

        params = {"query": {
            "type":
                {"$eq": u"oracle"},
            # "name": {"$eq": u"BOP_DB"}
            # "name": {"$eq": u"db-test-app"}
        },
            "fields": {
                "name": True,
                "_SERVICENODE.agentIp": True,
                "_SERVICENODE.port": True,
                "_SERVICENODE.type": True,
                "owner.name": True,
                "owner.nickname": True,
                "tester.name": True,
                "tester.nickname": True,
                "developer.name": True,
                "developer.nickname": True,
                "clusters.type": True,
                "type": True,
                "port": True,
                "featureRule": True,
                "featureEnabled": True

            }}

        if db_app_name:
            params['query']['name'] = {"$eq": db_app_name}
        dataList = http_post('POSTS', url, params)
        logging.info('获取DB应用数量为:%s' % len(dataList))

        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE="APP"))
        return dataList

    def getData(self):
        st = time.time()
        # 获取现网服务数据
        self.dataList = self.getAppNodeInfo()  # 获取应用信息

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def processingProServices(self, data, app_name, app_instanceId, app_port_list, pro_host_dict):
        """
        :param data: 应用全量数据
        :param app_name: 应用名称
        :param app_port: 服务端口
        :param pro_host_dict: 应用生产环境主机信息
        :return:
        """
        # --------------------------处理生产环境环境servernode信息
        # 1. 生产：user信息
        pro_user_list = []
        pro_add_existence = []  # 为了聚合去重
        owner = data.get('owner')
        if owner:
            for user in owner:
                name = user.get('name')
                nickname = user.get('nickname', '')
                if name in pro_add_existence:
                    continue
                pro_user_list.append({"name": name, "nickname": nickname, "type": u"运维"})
        logging.info('处理的应用名称:%s, 运维负责人数量为:%s， 用户信息:%s' % (app_name, len(pro_user_list), pro_user_list))

        # 2. 生产环境， 组合请求zcloud数据
        if pro_host_dict:
            pro_zcloud_data = {
                "jsonStr": {
                    "list": []
                }
            }
            for pro_ip, pro_host_info in pro_host_dict.items():

                # 循环遍历服务端口，组合_SERVICENODE信息
                node_info_list = []
                for port in app_port_list:
                    node_info = {
                        "app_instanceId": app_instanceId,
                        "DBAPP": app_name,
                        "agentIp": pro_ip,
                        "type": "oracle",
                        "port": int(port),
                        "USER": pro_user_list  # 应用负责人
                    }
                    node_info_list.append(node_info)

                data = {
                    "APP": [app_name],
                    "HOST": [pro_host_info],
                    "USER": pro_host_info.get('owner', []),  # 主机运维负责人
                    "_SERVICENODE": node_info_list
                }
                pro_zcloud_data['jsonStr']['list'].append(data)

            logging.info(
                '处理的应用名称:%s, 生产环境请求zcloud数据: %s' % (
                    app_name, json.dumps(pro_zcloud_data, sort_keys=True, indent=2)))

            # 4. 生产环境， 请求zcloud
            ret = http_post('POST', http_zcloud_url['pro'], headers=zcloud_headers['pro'],
                            params=pro_zcloud_data)
            print '处理的应用名称:%s----------------------------------- %s' % (app_name, ret)

        else:
            logging.info(u'处理的应用名称:%s, 生产环境主机没有节点信息' % app_name)
            # --------------------------处理生产环境环境servernode信息 end

    def processingTestServices(self, data, app_name, app_instanceId, app_port_list, uat_host_dict):
        """
        :param data: 应用全量数据
        :param app_name: 应用名称
        :param app_port: 服务端口
        :param uat_host_dict: 应用测试环境主机信息
        :return:
        """
        # --------------------------处理测试环境servernode信息
        # 1. 测试：user信息
        uat_user_list = []
        uat_add_existence = []  # user为了聚合去重
        tester = data.get('tester')
        if tester:
            for user in tester:
                name = user.get('name')
                nickname = user.get('nickname', '')
                if name in uat_add_existence:
                    continue
                uat_user_list.append({"name": name, "nickname": nickname, "type": u"测试"})
        logging.info('处理的应用名称:%s, 测试负责人数量为:%s， 用户信息:%s' % (app_name, len(uat_user_list), uat_user_list))

        # 3. 测试环境，组合请求zcloud数据
        if uat_host_dict:
            uat_zcloud_data = {
                "jsonStr": {
                    "list": []
                }
            }
            for uat_ip, uat_host_info in uat_host_dict.items():
                # 循环遍历服务端口，组合_SERVICENODE信息
                node_info_list = []
                for port in app_port_list:
                    node_info = {
                        "app_instanceId": app_instanceId,
                        "DBAPP": app_name,
                        "agentIp": uat_ip,
                        "type": "oracle",
                        "port": int(port),
                        "USER": uat_user_list  # 应用负责人
                    }
                    node_info_list.append(node_info)

                data = {
                    "APP": [app_name],
                    "HOST": [uat_host_info],
                    "USER": uat_host_info.get('owner', []),  # 主机运维负责人
                    "_SERVICENODE": node_info_list
                }
                uat_zcloud_data['jsonStr']['list'].append(data)

            logging.info(
                '处理的应用名称:%s, 测试环境请求zcloud数据: %s' % (app_name, json.dumps(uat_zcloud_data, sort_keys=True, indent=2)))

            # 4. 测试环境，发送zcloud请求
            ret = http_post('POST', http_zcloud_url['test'], headers=zcloud_headers['test'], params=uat_zcloud_data)
            print ret

        else:
            logging.info(u'处理的应用名称:%s, 测试环境主机没有节点信息' % app_name)

    def gevent_data(self, data):
        """
        :param i:  每个应用数据
        :return:
        """
        # print threading.enumerate() # 获取线程数量
        app_name = data.get('name')
        app_port = data.get('port')
        app_type = data.get('type')
        _SERVICENODE = data.get('_SERVICENODE')
        featureRule = data.get('featureRule')
        featureEnabled = data.get('featureEnabled')
        app_instanceId = data.get('instanceId')

        # 2.整理服务端口信息
        if "|" in app_port:
            app_port_list = [port.strip() for port in app_port.split("|")]
        else:
            app_port_list = [str(app_port).strip()]

        logging.info('开始处理的应用名称:%s, 应用类型为：%s' % (app_name, app_type))
        logging.info('处理的应用名称:%s, 服务端口为:%s' % (app_name, app_port_list))


        # 1.测试， 2生产
        clusters_info_list = data.get('clusters', [])
        if not clusters_info_list:
            logging.warning('处理的应用名称:%s，未创建集群信息！请创建集群纳管主机' % app_name)
            return
        if not app_port_list:
            logging.error('处理的应用名称:%s，设置应用服务端口属性，多个端口以|分割开' % app_name)
            return

        # 先获取主机信息
        try:
            url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="HOST")
            params = {"fields": {"ip": True, "save_type": True, "hardware_score": True,
                                 "idc": True, "osSystem": True, "osArchitecture": True, "sn": True, "memo": True,
                                 "_deviceList_CLUSTER.type": True, "owner.name": True, "owner.nickname": True},
                      "query": {"_deviceList_CLUSTER.appId.instanceId": {"$eq": app_instanceId}}}
            hostdataList = http_post('POST', url, params)
            inspect_data = hostdataList[0]  # 检查字段,报错就退出
        except Exception as e:
            logging.warning('处理的应用名称:%s，未纳管主机信息，请纳管主机信息' % app_name)
            return

        # 获取测试，生产主机信息
        uat_host_dict = {}  # ip: host_info
        pro_host_dict = {}
        for host_info in hostdataList:
            host_ip = host_info.get('ip')
            cluster_type = host_info.get('_deviceList_CLUSTER', [])[0]['type']  # 获取集群类型
            host_info.pop('_deviceList_CLUSTER')  # 删除集群信息
            if cluster_type == "1":
                host_info['_environment'] = 'test'
                uat_host_dict.update({host_ip: host_info})
            elif cluster_type == "2":
                host_info['_environment'] = 'pro'
                pro_host_dict.update({host_ip: host_info})
        logging.info(u'处理的应用名称:%s, 测试环境主机IP列表：%s' % (app_name, uat_host_dict.keys()))
        logging.info(u'处理的应用名称:%s, 生产环境主机IP列表：%s' % (app_name, pro_host_dict.keys()))

        # 处理生产环境
        self.processingProServices(data, app_name, app_instanceId, app_port_list, pro_host_dict)

        # 处理测试环境
        self.processingTestServices(data, app_name, app_instanceId, app_port_list, uat_host_dict)

        # 添加服务特征
        if len(app_port_list) > 1:
            app_port = '|'.join(app_port_list)

        if not featureEnabled:
            # 表示服务节点开关关闭
            node_auto = {"featurePriority": "500", "featureEnabled": "true",
                         "featureRule": [
                             {"key": "port", "method": "eq", "value": app_port, "label": "监听端口"}],
                         "instanceId": app_instanceId}
        elif str(featureRule[0]['value']) != str(app_port):
            # 表示端口不一致
            node_auto = {"featurePriority": "500", "featureEnabled": "true",
                         "featureRule": [
                             {"key": "port", "method": "eq", "value": app_port, "label": "监听端口"}],
                         "instanceId": app_instanceId}
        else:
            node_auto = False

        return node_auto

        # # pprint.pprint(ret, stream=None, indent=2, width=80)
        # zcloud_SERVICENODE = json.loads(ret.get('data'))['list'][0]['_SERVICENODE']
        #
        # # 类型分类
        # node_dict = {"mysql": []}
        # for node in zcloud_SERVICENODE:
        #     node_type = node.get('type')
        #     node_ip = node.get('agentIp')
        #     node_port = str(node.get('port'))
        #     node_name = node_ip + ":" + node_port
        #     node['name'] = node_name
        #     node['HOST'] = [host_dict.get(node_ip, [])]  # 主机
        #
        #     node.update(
        #         {"featurePriority": "500", "featureEnabled": "true",
        #          "featureRule": [{"key": "agentIp", "method": "eq", "value": node_ip, "label": "AgentIp"},
        #                          {"key": "port", "method": "eq", "value": node_port, "label": "监听端口"}]}
        #     )
        #
        #     # 处理是否被zcloud纳管
        #     zcloud_instance_id = node.get('zcloud_instance_id')
        #     if zcloud_instance_id:
        #         node['existence'] = u"是"
        #         # 处理是否是集群
        #         zcloud_is_cluster = node.get('zcloud_is_cluster', 0)
        #         if zcloud_is_cluster:
        #             node['zcloud_is_cluster'] = u"是"
        #         else:
        #             node['zcloud_is_cluster'] = u"否"
        #
        #         # 处理是否开发binlog
        #         zcloud_is_open_binlog = node.get('zcloud_is_open_binlog', 0)
        #         if zcloud_is_open_binlog:
        #             node['zcloud_is_open_binlog'] = u"是"
        #         else:
        #             node['zcloud_is_open_binlog'] = u"否"
        #
        #     else:
        #         node['existence'] = u"否"
        #
        #     if node_type == 'mysql':
        #         node['APP_MYSQL_SERVICE'] = [app_instanceId]  # 关联应用
        #         node_dict["mysql"].append(
        #             node
        #         )
        # return node_dict

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        data = {
            "keys": ['instanceId'],
            "datas": []
        }

        for i, g in enumerate(res):
            if g.value:
                data['datas'].append(g.value)

        if len(data['datas']):
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID="APP")
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
    AutoAppServiceNode()
    # InstanceCluster("MYSQL_SERVICE", "MYSQL")
