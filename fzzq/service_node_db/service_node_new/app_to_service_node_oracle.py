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
import threading, logging, sys, copy, datetime
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

# 携程池-开始清理僵尸数据，清理大于 2 天的数据
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

cmdb_host = "10.163.128.232"
easyops_org = "3087"
# db_app_name = '新意资金结算系统_DB'
# del_day = 2

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
                else:
                    logging.error("code: %s, url: %s" % (str(r.status_code), url))
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
            r = requests.delete(url, headers=headers, timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                return data
            else:
                return r.content
        except Exception as e:
            return e


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

    # 生产环境-请求zcloud
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
                user_instanceId = user.get('instanceId')
                if name in pro_add_existence:
                    continue
                pro_user_list.append(
                    {"name": name, "nickname": nickname, "type": u"运维", "user_instanceId": user_instanceId})
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
                        "USER": pro_user_list,  # 应用负责人
                        "ZCLOUD": u"生产环境"
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
            try:
                ret = http_post('POST', http_zcloud_url['pro'], headers=zcloud_headers['pro'],
                                params=pro_zcloud_data)
                logging.info(
                    '处理的应用名称:%s, 生产环境zcloud返回的zcloud数据----------------------------------- %s' % (app_name, ret))

                logging.info('-----------------处理的应用名称:%s, 开始处理zcloud返回数据------------------' % app_name)
                examples_cleaning_list = self._deal_zcloud_pro_uat_data(pro_zcloud_data, app_name, ret, u"生产")
            # 考虑zcloud连接失败
            except Exception as e:
                examples_cleaning_list = self._zcloud_error_init_cmdb_data(pro_zcloud_data, u'生产')
                logging.info(
                    '处理的应用名称:%s, 生产环境请求zcloud数据连接失败，cmdb进行初始化工作完成，结果为:%s ' % (app_name, examples_cleaning_list))

            return examples_cleaning_list

        else:
            logging.info(u'处理的应用名称:%s, 生产环境主机没有节点信息' % app_name)
            return []
            # --------------------------处理生产环境环境servernode信息 end

    # 测试环境-请求zcloud
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
                user_instanceId = user.get('instanceId')
                if name in uat_add_existence:
                    continue
                uat_user_list.append(
                    {"name": name, "nickname": nickname, "type": u"测试", "user_instanceId": user_instanceId})
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
                        "USER": uat_user_list,  # 应用负责人
                        "ZCLOUD": u"测试环境"
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
            try:
                ret = http_post('POST', http_zcloud_url['test'], headers=zcloud_headers['test'], params=uat_zcloud_data)
                logging.info(
                    '处理的应用名称:%s, 测试环境zcloud返回的zcloud数据----------------------------------- %s' % (app_name, ret))

                logging.info('-----------------处理的应用名称:%s, 开始处理zcloud返回数据------------------' % app_name)
                examples_cleaning_list = self._deal_zcloud_pro_uat_data(uat_zcloud_data, app_name, ret, u"测试")

            # 考虑zcloud连接失败
            except Exception as e:
                examples_cleaning_list = self._zcloud_error_init_cmdb_data(uat_zcloud_data, u'测试')
                logging.info(
                    '处理的应用名称:%s, 测试环境请求zcloud数据连接失败，cmdb进行了初始化工作完成，结果为:%s ' % (app_name, examples_cleaning_list))
            return examples_cleaning_list

        else:
            logging.info(u'处理的应用名称:%s, 测试环境主机没有节点信息' % app_name)
            return []

    def _deal_zcloud_pro_uat_data(self, cmdb_repo_data, app_name, ret, host_type):
        """
        :param cmdb_repo_data: cmdb请求zcloud数据
        :param app_name: 应用名称
        :param ret: zcloud返回的数据
        :param host_type: 环境类型，生产，测试
        :return:
        """
        ret_node_list = []
        try:
            zcloud_ret_data_list = json.loads(ret.get('data'))['list']
            for data in zcloud_ret_data_list:
                _SERVICENODE = data.get('_SERVICENODE')  # 节点列表
                ret_host_list = data.get('HOST')  # 主机信息 list

                # 处理主机信息以IP 和实例ID为字典
                host_id_dict = {}
                for host in ret_host_list:
                    host_instanceId = host.get('instanceId')
                    host_ip = host.get('ip')
                    if not host_id_dict.has_key(host_ip):
                        host_id_dict[host_ip] = []
                    host_id_dict[host_ip].append(host_instanceId)

                for server_node_data in _SERVICENODE:
                    try:
                        # 应用用户信息 list
                        ret_user_list = server_node_data.get('USER')

                        # 处理负责人信息
                        user_list = []
                        for user in ret_user_list:
                            user_list.append(user.get('user_instanceId'))
                    except Exception as e:
                        logging.warning(u'处理的应用名称:%s, %s环境处理zcloud返回数据，其中用户信息为空' % (app_name, host_type))
                        user_list = []

                    # 获取基本信息
                    app_instanceId = [server_node_data.get('app_instanceId')]
                    node_ip = server_node_data.get('agentIp')
                    node_port = str(server_node_data.get('port'))  # int
                    node_name = node_ip + ":" + node_port

                    zcloud_service_node = server_node_data.get('zcloud_service_node')  # zcloud返回的数据list
                    for node in zcloud_service_node:
                        node['name'] = node_name
                        node['agentIp'] = node_ip
                        node['port'] = int(node_port)
                        node['type'] = 'oracle'
                        # 处理是否被zcloud纳管
                        zcloud_instance_id = node.get('zcloud_instance_id')
                        if zcloud_instance_id:
                            node['existence'] = u"是"
                            # 处理是否是集群
                            zcloud_is_cluster = node.get('zcloud_is_cluster', 0)
                            if zcloud_is_cluster:
                                node['zcloud_is_cluster'] = u"是"
                            else:
                                node['zcloud_is_cluster'] = u"否"

                            try:
                                # # 处理zcloud_config_info配置信息
                                # # 服务名
                                # # 监听列表
                                # # 监听日志路径
                                zcloud_config_info = node.get('zcloud_config_info', [])
                                new_zcloud_config_info = []  # 去掉监听列表的新配置文件
                                listener_list = []
                                if zcloud_config_info:
                                    for config in zcloud_config_info:
                                        # {u'value': (u'SYS$BACKGROUND', u'SYS$USERS', u'icsdb3'), u'key': u'service_name', u'label': u'\u670d\u52a1\u540d'}
                                        key = config.get('key')
                                        value = config.get('value', [])
                                        if key == 'listener_list':
                                            listener_list = value
                                            #  'value': [{
                                            # 					u 'port': u '1521',
                                            # 					u 'listen_name': u 'LISTENER'
                                            # 				}]
                                            continue

                                        value = config.get('value', [])
                                        config['value'] = ",".join(value)
                                        new_zcloud_config_info.append(config)
                                    node['zcloud_config_info'] = new_zcloud_config_info
                                    node['listener_list'] = listener_list

                            except Exception as e:
                                logging.error(u'处理的应用名称:%s, %s环境处理zcloud返回数据 ' % (app_name, e))

                        else:
                            node['existence'] = u"否"
                            # 更新时间
                            now_time = datetime.datetime.now()
                            node['zcloud_update_time'] = datetime.datetime.strftime(now_time, '%Y-%m-%d %H:%M:%S')

                        # 处理关联关系
                        node['host_type'] = host_type
                        node['APP_ORACLE_SERVICE'] = app_instanceId
                        node['HOST'] = host_id_dict.get(node_ip, [])
                        node['USER'] = user_list

                        # 增加服务节点发现规则
                        node.update({"featurePriority": "500", "featureEnabled": "true",
                                     "featureRule": [
                                         {"key": "port", "method": "eq", "value": node_port, "label": u"监听端口"},
                                         {"key": "agentIp", "label": "AgentIp", "method": "eq", "value": node_ip}

                                     ]})

                        ret_node_list.append(node)
                        logging.info(u'处理的应用名称:%s, %s环境处理zcloud返回数据，即将入库的数据: %s' % (
                            app_name, host_type, json.dumps(node, sort_keys=True, indent=2)))

        # 考虑zcloud返回数据失败
        except Exception as e:
            logging.error('处理的应用名称:%s, 清理zcloud数据错误%s--------ret:%s' % (app_name, e, ret))
            ret_node_list = self._zcloud_error_init_cmdb_data(cmdb_repo_data, host_type)

        return ret_node_list

    def _zcloud_error_init_cmdb_data(self, cmdb_repo_data, host_type):
        """
        zcloud连接失败，或者返回数据异常，cmdb需要初始化数据
        :param cmdb_repo_data: cmdb请求zcloud所有数据
        :param host_type: 环境类型
        :return:
        """
        ret_list = []
        try:
            cmdb_repo_data_list = cmdb_repo_data.get('jsonStr')['list']
            for ret in cmdb_repo_data_list:
                data = {}
                service_node_list = ret.get('_SERVICENODE')
                for node in service_node_list:
                    app_instanceId = node.get('app_instanceId')
                    agentIp = node.get('agentIp')
                    port = node.get('port')
                    type = node.get('type')
                    name = agentIp + ":" + str(port)
                    user_list = node.get('USER')
                    user_instanceId_list = [user.get('user_instanceId', '') for user in user_list]
                    data['name'] = name
                    data['type'] = type
                    data['agentIp'] = agentIp
                    data['USER'] = user_instanceId_list
                    data['APP_ORACLE_SERVICE'] = app_instanceId
                    data['existence'] = u'否'

                    data.update({"featurePriority": "500", "featureEnabled": "true",
                                 "featureRule": [
                                     {"key": "port", "method": "eq", "value": port, "label": u"监听端口"},
                                     {"key": "agentIp", "label": "AgentIp", "method": "eq", "value": agentIp}

                                 ]})

                host_info = ret.get('HOST')
                host_instanceId_list = [host.get('instanceId', '') for host in host_info]
                data['HOST'] = host_instanceId_list
                data['host_type'] = host_type

                # 更新时间
                now_time = datetime.datetime.now()
                data['zcloud_update_time'] = datetime.datetime.strftime(now_time, '%Y-%m-%d %H:%M:%S')

                ret_list.append(data)

        # 处理数据失败
        except Exception as e:
            logging.error(e)

        return ret_list

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
                host_info['_environment'] = u'测试环境'
                uat_host_dict.update({host_ip: host_info})
            elif cluster_type == "2":
                host_info['_environment'] = u'生产环境'
                pro_host_dict.update({host_ip: host_info})
        logging.info(u'处理的应用名称:%s, 测试环境主机IP列表：%s' % (app_name, uat_host_dict.keys()))
        logging.info(u'处理的应用名称:%s, 生产环境主机IP列表：%s' % (app_name, pro_host_dict.keys()))

        # 处理生产环境
        examples_cleaning_list_pro = self.processingProServices(data, app_name, app_instanceId, app_port_list,
                                                                pro_host_dict)

        # 处理测试环境
        examples_cleaning_list_uat = self.processingTestServices(data, app_name, app_instanceId, app_port_list,
                                                                 uat_host_dict)

        # 添加服务特征
        if len(app_port_list) > 1:
            app_port = '|'.join(app_port_list)

        if not featureEnabled:
            # 表示服务节点开关关闭
            node_auto = {"featurePriority": "500", "featureEnabled": "true",
                         "featureRule": [
                             {"key": "port", "method": "eq", "value": app_port, "label": "监听端口"}]}
        elif str(featureRule[0]['value']) != str(app_port):
            # 表示端口不一致
            node_auto = {"featurePriority": "500", "featureEnabled": "true",
                         "featureRule": [
                             {"key": "port", "method": "eq", "value": app_port, "label": "监听端口"}]}
        else:
            node_auto = False

        # 更新应用的服务节点规则
        if node_auto:
            url = "http://{HOST}/object/APP/instance/{app_id}".format(HOST=cmdb_host, app_id=app_instanceId)
            code, ret = http_post('PUT', url, node_auto)
            logging.info(u'处理的应用名称:%s, 更新应用的服务节点规则： %s' % (app_name, ret))

        ret_data = examples_cleaning_list_pro + examples_cleaning_list_uat
        return ret_data

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
            if g.value:  # list
                data['datas'] += g.value

        if len(data['datas']):
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID="ORACLE_SERVICE")
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


# 清理僵尸数据
class CleanUpData():
    def __init__(self):
        logging.info('------------------------开始清理僵尸数据，清理大于 %s 天的数据------------------------' % del_day)
        self.data = self.getData()  # 现网数据
        self.task()

    def getAppNodeInfo(self):
        """
        获取 应用信息,服务节点信息，主机信息
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="ORACLE_SERVICE")

        params = {"query": {},

                  "fields": {
                      "name": True,
                      "zcloud_update_time": True
                  }}

        if db_app_name:
            params['query']['APP_ORACLE_SERVICE.name'] = {"$eq": db_app_name}

        dataList = http_post('POSTS', url, params)
        logging.info('获取%s应用关联的数据数量为:%s' % (db_app_name, len(dataList)))

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

    def gevent_data(self, data):
        """
        :param data:  每个应用数据
        :return:
        """
        # print threading.enumerate() # 获取线程数量
        now_time = datetime.datetime.now()
        zcloud_update_time = data.get("zcloud_update_time")
        zcloud_update_time = datetime.datetime.strptime(zcloud_update_time, "%Y-%m-%d %H:%M:%S")
        diff_day = (now_time - zcloud_update_time).days
        # 表示改条实例del_day内没有汇报过数据
        if diff_day >= del_day:
            instanceId = data.get('instanceId')
            name = data.get('name')
            logging.info('实例名称:%s, %s 天没汇报数据，将被删除' % (name, str(diff_day)))
            return instanceId

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        del_instanceIds_list = []
        for i, g in enumerate(res):
            if g.value:  # list
                del_instanceIds_list.append(g.value)

        if del_instanceIds_list:
            del_instanceIds_str = ";".join(del_instanceIds_list)
            url = "http://{HOST}/object/{ID}/instance/_batch?instanceIds={DEL_STR}".format(HOST=cmdb_host,
                                                                                           ID="ORACLE_SERVICE",
                                                                                           DEL_STR=del_instanceIds_str)
            time.sleep(1)
            res = http_post('DELETE', url)
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
    # 清理垃圾数据
    CleanUpData()
