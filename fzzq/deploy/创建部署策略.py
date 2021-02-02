# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: new.py
@time: 2020/12/7 15:16
@desc: 新版创建部署策略
'''
import json, requests
import logging
import sys

reload(sys)
sys.setdefaultencoding('utf8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# CMDB配置
deploy_host = EASYOPS_CMDB_HOST.split(':')[0] + ':8061'
cmdb_host = EASYOPS_CMDB_HOST.split(':')[0]
# deploy_host = '192.168.28.28:8061'
# cmdb_host = '192.168.28.28'

easyops_org = str(EASYOPS_ORG)
# easyops_org = '9070'
easy_user = 'defaultUser'
# header配置

deploy_headers = {'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}
cmdb_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': easy_user,
                'content-Type': 'application/json'}

app_name = name


# app_name = 'test'

# 0 开发， 1测试  2生产
# clusterNum = "2"


class EasyopsPubic(object):

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, headers, cmdb_host, params={}):
        page_size = 100
        if not params.has_key('page_size'):
            params['page_size'] = page_size

        url = u'http://{easy_host}{restful_api}'.format(easy_host=cmdb_host, restful_api=restful_api)

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
                                method='post_page',
                                headers=headers,
                                cmdb_host=cmdb_host
                            )
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
                                method='get_page',
                                headers=headers,
                                cmdb_host=cmdb_host
                            )
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

        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['code']
            except Exception as e:
                return {"list": []}


class CreatePackageInfo(EasyopsPubic):
    """
    创建部署策略
    1. 根据应用获取主机信息，只获取生产环境的
    1.1 需要主机的name，id， 对应的集群信息

    2. 获取应用信息，需要name， id
    3。 获取包信息，需要id，name
    """

    def __init__(self):
        self.run()

    # 获取部署策略信息，并部署
    def get_strategy_info(self, data):
        """
        获取策略信息,并生成部署策略
        :return:
        """
        APP_InstanceId = data.get('app_info')['APP_InstanceId']
        logging.info('Start to get the application ID of deployment policy information: %s' % APP_InstanceId)
        try:

            # 部署策略信息
            deploy_policy_list = self.http_post('get_page', '/deployStrategy?appId=' + APP_InstanceId, deploy_headers,
                                                deploy_host)
            logging.info('APP: %s, Deployment policy information' % APP_InstanceId)

            # 判断参数。
            all_deploy = False
            only_one = False
            only_other = False

            for deploy_policy in deploy_policy_list:  # 循环遍历部署策略
                if deploy_policy.get('clusterType') == clusterNum:  # 判断部署策略是否对应上环境类型 开发-开发 生产-生产
                    name = str(deploy_policy.get('name'))
                    logging.info('APP: %s, Deployment policy name %s' % (APP_InstanceId, name))
                    if name == u'全量部署':
                        all_deploy = True
                        self.update_deploy(data, deploy_policy, 'all')
                    elif name == u'灰度1台机器部署':
                        only_one = True
                        self.update_deploy(data, deploy_policy, 'one')
                    elif name == u'灰度其他机器部署':
                        only_other = True
                        self.update_deploy(data, deploy_policy, 'other')

            # 说明没有部署策略，需要创建
            if not all_deploy:
                logging.info('Start creating full deployment policy...')
                self.create_policy(data, 'all')
            if not only_one:
                logging.info('Start creating 1 machine deployment...')
                self.create_policy(data, 'one')
            if not only_other:
                logging.info('Start creating other machine deployment...')
                self.create_policy(data, 'other')

        except Exception as e:
            logging.error('error get_strategy_info fiald %s' % e)

    # 获取应用信息
    def get_app_info(self):
        """
        获取应用信息
        :return:
        """
        ret_info = dict()
        try:
            params = {
                "query": {
                    "name": {"$eq": app_name},
                },
                "fields": {
                    "instanceId": True,
                    "name": True,
                    'clusters.name': True,  # 集群信息
                    'clusters.type': True,  # 集群信息
                    'clusters.deviceList.hostname': True,  # 集群信息
                    'clusters.deviceList.instanceId': True,  # 集群信息
                    'clusters.deviceList.ip': True,  # 集群信息
                },
                "page_size": 1

            }
            logging.info('Query application parameters info: %s' % params)
            ret = self.http_post('post_page', '/object/APP/instance/_search', cmdb_headers, cmdb_host, params)
            logging.info('Query application results info: %s' % ret)
            total = ret.get('total')
            if total == 0:
                logging.error('The query application result is 0, total is %s', total)
                return False
            ret = ret['list'][0]

            clusters = ret.get('clusters')  # 集群信息
            if not clusters:
                logging.error('Application system cluster information configuration error %s' % clusters)
                return False

            # 处理应用信息
            logging.info('Start collecting and processing application information')
            ret_info.update(
                {"app_info": {
                    "APP_InstanceId": ret.get('instanceId'),
                    "APP_NAME": ret.get('name'),
                }}
            )
            logging.info('success')

            # 处理集群信息
            logging.info('Start gathering and processing cluster information')
            cluster_info = []  # 集群list信息
            for cluster in clusters:
                if str(cluster['type']) == str(clusterNum):
                    cluster_name = cluster['name']
                    cluster_instanceId = cluster['instanceId']
                    cluster_type = cluster['type']
                    # 删除多余信息，重新组合信息
                    del cluster['_object_id']
                    del cluster['name']
                    del cluster['instanceId']
                    del cluster['type']
                    cluster.update({
                        "cluster_name": cluster_name,
                        "cluster_instanceId": cluster_instanceId,
                        "cluster_type": cluster_type,
                    })
                    cluster_info.append(cluster)

            ret_info.update({
                "cluster_info": cluster_info
            })

            logging.info('success')

            # 获取程序包信息,处理程序包信息
            logging.info('Start gathering process package information')
            package_info = self.get_package_info()
            if not package_info:
                logging.error('Error getting package information error %s' % package_info)
                return False

            ret_info.update(
                **package_info
            )
            logging.info('success')

            logging.info('Host information of cleaned application cluster :%s' % ret_info)
            return ret_info
        except Exception as e:
            logging.error('error get_app_info fiald %s' % e)

    # 获取程序包信息
    def get_package_info(self):
        """
        获取包信息
        :return:
        """
        try:
            search_headers = {
                'host': "deploy.easyops-only.com",
                'org': easyops_org,
                'user': easy_user
            }
            search_url = '/package/search?page=1&pageSize=10&name={app}&exact=true'.format(app=app_name)

            logging.info('search package params info: %s' % search_url)
            logging.info('search package headers info: %s' % search_headers)

            ret = self.http_post('get_page', search_url, search_headers, cmdb_host)

            logging.info('package ret info: %s' % ret)
            total = ret.get('total')
            if total == 0:
                logging.error('package ret is null, total is %s', total)
                return False

            ret = ret['list'][0]
            lastVersionInfo = ret.get('lastVersionInfo')
            ret_info = {}

            if not lastVersionInfo:
                logging.error('Please create the package version or initialize the package first')
                return False
            try:
                package_name = ret.get('name')
                package_type = ret.get('type')
                package_installPath = ret.get('installPath')  # 部署路径
                packageId = ret.get('packageId')  # 包ID
                platform = ret.get('platform')  # 环境类型，linux， win

                ret_info.update(
                    {"package_info":
                         {"name": package_name,
                          "type": package_type,
                          "installPath": package_installPath,
                          "packageId": packageId,
                          "platform": platform, }
                     }
                )
                logging.info('search package info %s', ret_info)
                return ret_info
            except Exception as e:
                logging.error('get package info filed %s' % e)
                return False
        except Exception as e:
            logging.error('error get_package_info fiald %s' % e)

    # 创建部署策略
    def create_policy(self, data, status):
        package_info = data.get('package_info')
        cluster_info_list = data.get('cluster_info')  # list
        app_info = data.get('app_info')
        APP_InstanceId = app_info.get('APP_InstanceId')
        try:
            pars = {
                "apiVersion": "alphav1",
                "scope": "target",
                "targetList": [],
                "clusterType": clusterNum,
                "name": "test",
                "type": "default",
                "app": {

                },
                "batchStrategy": {
                    "type": "autoBatch",
                    "autoBatch": {
                        "batchNum": 1,
                        "batchInterval": 3,
                        "failedStop": False
                    },
                    "manualBatch": {
                        "batchNum": 1,
                        "batchInterval": 3,
                        "batches": [],
                        "failedStop": False
                    }
                },
                "packageList": [
                ]
            }

            host_cluter_all_list = []
            for cluster_info in cluster_info_list:
                host_info = cluster_info.get('deviceList')  # 主机列表

                if not host_info:
                    logging.error(
                        'APP: %s, Fully deploy the policy to check whether the cluster host information exists' % (
                            APP_InstanceId))
                    continue

                # 集群信息
                clusterId = cluster_info.get('cluster_instanceId')
                cluster_name = cluster_info.get('cluster_name')
                cluster_type = cluster_info.get('cluster_type')

                targetinfo = []
                for host in host_info:
                    host_id = host.get('instanceId')
                    host_name = host.get('hostname')
                    host_ip = host.get('ip')
                    targetinfo.append(
                        {
                            "instanceId": host_id,
                            "name": host_name,
                            "targetId": host_ip,
                            "targetName": host_ip,
                            "cluster": {
                                "clusterId": clusterId,
                                "name": cluster_name,
                                "type": cluster_type
                            }
                        }
                    )

                host_cluter_all_list += targetinfo

            logging.info('APP: %s Number of machines to create deployment policy %s' % (
                APP_InstanceId, len(host_cluter_all_list)))
            if len(host_cluter_all_list) == 0:
                logging.error('The number of deployed cluster hosts is :%s, Set host' % len(host_cluter_all_list), )
                return

            if status == 'all':
                pars['name'] = str('全量部署')
                pars['targetList'] = host_cluter_all_list
            elif status == 'one':
                pars['name'] = str('灰度1台机器部署')
                if len(host_cluter_all_list) == 1:
                    pars['targetList'] = [host_cluter_all_list[0]]
                else:
                    pars['targetList'] = [host_cluter_all_list[0]]
            elif status == 'other':
                pars['name'] = str('灰度其他机器部署')
                if len(host_cluter_all_list) == 1:
                    pars['targetList'] = [host_cluter_all_list[0]]
                else:
                    pars['targetList'] = host_cluter_all_list[1:]

            logging.info(
                'APP: %s, Create the name of the deployment policy: %s' % (APP_InstanceId, pars['name']))

            pars['app'] = {
                "name": app_info['APP_NAME'],
                "appId": APP_InstanceId,
            }
            logging.info('APP: %s ,Deployment application information info is %s' % (APP_InstanceId, pars.get('app')))

            pack_data = {
                "targetVersion": "$latest",
                "cluster": None,
                "preStop": True,
                "postRestart": True,
                "fullUpdate": False,
                "autoStart": True,
                "userCheck": True
            }

            package_info.update(**pack_data)
            pars['packageList'] = [package_info]

            logging.info(
                'APP: %s, Deployment policy all information info is: %s' % (APP_InstanceId, pars['packageList']))

            ret = self.http_post('post_page', '/deployStrategy', deploy_headers, deploy_host, pars)
            logging.info('APP: %s, result is %s' % (APP_InstanceId, ret))

        except Exception as e:
            logging.error('APP: %s, error create_policy fiald %s' % (APP_InstanceId, e))

    # 更新部署策略
    def update_deploy(self, data, deploy_policy, status):
        """
        :param data: 现网应用信息
        :param deploy_policy: 部署策略信息
        :return:
        """
        logging.info('Start updating deployment policy....')
        # 现网数据
        cluster_info_list = data.get('cluster_info')  # list

        update_targetList_info = []
        for cluster_info in cluster_info_list:
            cluster_type = cluster_info.get('cluster_type')  # 现网集群类型
            cluster_instanceId = cluster_info.get('cluster_instanceId')  # 现网集群id
            cluster_name = cluster_info.get('cluster_name')  # 现网集群名称
            deviceList = cluster_info.get('deviceList')  # 现网主机数据
            logging.info('Host information of current network cluster...%s' % deviceList)

            # 直接拿现网数据覆盖策略数据
            for device in deviceList:
                device_host_instanceId = device.get('instanceId')
                device_host_ip = device.get('ip')

                ret = {
                    'instanceId': device_host_instanceId,
                    'targetName': device_host_ip,
                    'targetId': device_host_ip,
                    'cluster': {
                        'type': str(cluster_type),
                        'clusterId': cluster_instanceId,
                        'name': cluster_name
                    }
                }
                update_targetList_info.append(ret)

        if status == 'all':
            deploy_policy['targetList'] = update_targetList_info
        elif status == 'one':
            deploy_policy['targetList'] = [update_targetList_info[0]]
        elif status == 'other':
            if len(update_targetList_info) == 1:
                deploy_policy['targetList'] = [update_targetList_info[0]]
            else:
                deploy_policy['targetList'] = update_targetList_info[1:]

        del deploy_policy['status']

        # 策略数据
        deploy_id = deploy_policy.get('id')
        logging.info('deployment policy ID : %s' % deploy_id)

        ret = self.http_post('put', '/deployStrategy/{id}'.format(id=deploy_id), deploy_headers, deploy_host,
                             params=deploy_policy)
        if ret != 0:
            logging.error('deployment of update policy failed')
        logging.info('deployment of update strategy succeeded')

    def run(self):
        try:
            app_info = self.get_app_info()
            if not app_info:
                logging.error('Error getting data information')
                return

            # 生产部署策略
            logging.info('Getting deployment policy information')
            strategy_info = self.get_strategy_info(app_info)

        except Exception as e:
            logging.error('error %s' % e)
            logging.error('app name is', app_name)


if __name__ == '__main__':
    CreatePackageInfo()
