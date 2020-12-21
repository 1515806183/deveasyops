# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 创建灰度部署策略.py
@time: 2020/12/7 15:16
@desc: 自动创建部署策略_单机版
'''
import json, requests
import logging
import sys
import copy

reload(sys)
sys.setdefaultencoding('utf8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# CMDB配置
# deploy_host = '28.163.0.123:8061'
# cmdb_host = "28.163.0.123"
deploy_host = '28.163.0.123:8061'
cmdb_host = "28.163.0.123"

easyops_org = '3087'
easy_user = 'defaultUser'
# header配置

deploy_headers = {'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}
cmdb_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': easy_user,
                'content-Type': 'application/json'}

app_name = 'secured_ifc-index-dubbo-service'

# 0 开发， 1测试  2生产
clusterNum = "2"


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
                print e
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

        # PUT
        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params), timeout=60)
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

    def get_strategy_info(self):
        """
        获取策略信息,并生成部署策略
        :return:
        """
        try:
            if self.appInstanceId:

                ret_list = self.http_post('get_page', '/deployStrategy?appId=' + self.appInstanceId, deploy_headers,
                                          deploy_host)

                only_one = False
                only_other = False
                all_deploy = False
                for ret in ret_list:
                    if ret.get('clusterType') == clusterNum:
                        name = str(ret.get('name'))
                        logging.info('strategy_info name %s %s' % (name, ret.get('clusterType')))
                        if name == u'全量部署':
                            all_deploy = True
                        if name == u'灰度1台机器部署':
                            only_one = True
                        elif name == u'灰度其他机器部署':
                            only_other = True

                # 说明没有灰度1台机器部署策略，需要创建
                if not all_deploy:
                    logging.info('all_deploy start...')
                    self.all_deploy()

                if not only_one:
                    logging.info('create_one start...')
                    self.create_one()

                if not only_other:
                    logging.info('create_other start...')
                    self.create_other()
        except Exception as e:
            logging.error('error get_strategy_info fiald %s' % e)

    def get_cluster_host_info(self):
        """
        根据应用获取主机和集群信息
        :return:
        """
        try:
            self.appInstanceId = self.app_info.get('appId')
            if self.appInstanceId:
                params = {
                    "fields": {
                        "name": True,
                        "type": True,
                        "deviceList.hostname": True,
                        "deviceList.instanceId": True,
                        "deviceList.ip": True,
                    },
                    "query": {
                        "$and": [{
                            "appId.instanceId": {
                                "$eq": self.appInstanceId
                            }
                        }, {
                            "_deployType": {
                                "$eq": "default"
                            }
                        }]
                    }
                }
                logging.info('CLUSTER app params info: %s' % params)
                ret_cluster = self.http_post('post_page', '/object/CLUSTER/instance/_search', cmdb_headers, cmdb_host,
                                             params)

                # 遍历集群列表
                logging.info('CLUSTER ret_cluster: %s' % ret_cluster)
                for clusters in ret_cluster.get('list'):
                    if clusters.get('type') == clusterNum:
                        logging.info('cluster == %s  info = %s' % (clusterNum, clusters))
                        del clusters['_object_id']
                        logging.info('CLUSTER info: %s' % clusters)
                        return clusters
                else:
                    return False

            else:
                return False
        except Exception as e:
            logging.error('error get_cluster_host_info fiald %s' % e)

    def get_app_info(self):
        """
        获取应用信息
        :return:
        """
        try:
            params = {
                "query": {
                    "name": {"$eq": app_name},
                },
                "fields": {
                    "instanceId": True,
                    "name": True,

                },
                "page_size": 1

            }
            logging.info('search app params info: %s' % params)
            ret = self.http_post('post_page', '/object/APP/instance/_search', cmdb_headers, cmdb_host, params)
            logging.info('app info: %s' % ret)
            total = ret.get('total')
            if total == 0:
                logging.info('app ret is null, total is %s', total)
                return False

            ret = ret.get('list')[0]
            ret.pop('_object_id')
            ret.update({'appId': ret.get('instanceId')})
            ret.pop('instanceId')
            logging.info('new app info %s', ret)
            return ret
        except Exception as e:
            logging.error('error get_app_info fiald %s' % e)

    def get_package_info(self):
        """
        获取包信息
        :return:
        """
        try:
            params = {
                "query": {
                    "name": {"$eq": app_name},
                },
                "fields": {
                    "name": True,
                    "installPath": True,
                    "packageId": True,
                    "platform": True,
                    "type": True
                },
                "page_size": 1

            }
            logging.info('search package params info: %s' % params)
            ret = self.http_post('post_page', '/object/GQPACAGE/instance/_search', cmdb_headers, cmdb_host, params)
            logging.info('package info: %s' % ret)
            total = ret.get('total')

            if total == 0:
                logging.info('package ret is null, total is %s', total)
                return False
            ret = ret.get('list')[0]
            ret.pop('_object_id')
            ret.update({'packageName': ret.get('name')})
            ret.pop('name')
            ret.pop('instanceId')
            logging.info('new app info %s', ret)
            return ret
        except Exception as e:
            logging.error('error get_package_info fiald %s' % e)

    def all_deploy(self):
        """
        创建全量部署策略
        :return:
        """
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
                    #     {
                    #     "packageId": "5d672bfdf36fdd70472f93d933a8d679",
                    #     "packageName": "founder-demo",
                    #     "installPath": "/tmp/founder-demo",
                    #     "type": "1",
                    #     "platform": "linux",
                    #
                    #     "targetVersion": "$latest",
                    #     "cluster": None,
                    #     "preStop": True,
                    #     "postRestart": True,
                    #     "fullUpdate": False,
                    #     "autoStart": True,
                    #     "userCheck": True
                    # }
                ]
            }

            cluster_host_info_all = copy.deepcopy(self.cluster_host_info)  # 集群主机信息
            host_info = cluster_host_info_all.get('deviceList')  # 主机列表

            # 集群信息
            clusterId = cluster_host_info_all.get('instanceId')
            name = cluster_host_info_all.get('name')
            type = cluster_host_info_all.get('type')

            targetinfo = []
            for host in host_info:
                host_id = host.get('instanceId')
                host_name = host.get('hostname')
                ip = host.get('ip')
                targetinfo.append(
                    {
                        "instanceId": host_id,
                        "name": host_name,
                        "targetId": ip,
                        "targetName": ip,
                        "cluster": {
                            "clusterId": clusterId,
                            "name": name,
                            "type": type
                        }
                    }
                )

            pars['targetList'] = targetinfo
            logging.info('all_deploy targetList is %s' % pars.get('targetList'))

            app_info = copy.deepcopy(self.app_info)
            pars['app'] = app_info
            logging.info('all_deploy app info is %s' % pars.get('app'))

            pack_data = {
                "targetVersion": "$latest",
                "cluster": None,
                "preStop": True,
                "postRestart": True,
                "fullUpdate": False,
                "autoStart": True,
                "userCheck": True
            }
            package_info = copy.deepcopy(self.package_info)
            package_info.update(**pack_data)
            pars['packageList'] = [package_info]
            logging.info('all_deploy packageList info  is %s' % pars['packageList'])

            pars['name'] = str('全量部署')

            logging.info('all_deploy name  is %s' % pars['name'])

            ret = self.http_post('post_page', '/deployStrategy', deploy_headers, deploy_host, pars)

            logging.info('all_deploy ret  is %s' % ret)

        except Exception as e:
            logging.error('error all_deploy fiald %s' % e)

    def create_one(self):
        """
        组合 部署策略参数,并创建策略
        {
            "apiVersion": "alphav1",
            "scope": "target",
            "targetList": [{
                "instanceId": "59617b9d29242",
                "name": "demo-flow",
                "cluster": {
                    "clusterId": "5b39004964134",
                    "name": "founder-demo-dev",
                    "type": "0"
                }
            }], 从集群那里拿
            "clusterType": "0",
            "name": "test",
            "type": "default",
            "app": {
                "name": "Founder-Demo",
                "appId": "5b39002ac7bf6"
            }, 应用那里拿
            "batchStrategy": {
                "type": "autoBatch",
                "autoBatch": {
                    "batchNum": 1,
                    "batchInterval": 3,
                    "failedStop": false
                },
                "manualBatch": {
                    "batchNum": 1,
                    "batchInterval": 3,
                    "batches": [],
                    "failedStop": false
                }
            }, 默认
            "packageList": [{
                "packageId": "5d672bfdf36fdd70472f93d933a8d679",
                "packageName": "founder-demo",
                "installPath": "/tmp/founder-demo",
                "type": "1",
                "targetVersion": "$latest",
                "platform": "linux",
                "cluster": null,
                "preStop": true,
                "postRestart": true,
                "fullUpdate": false,
                "autoStart": true,
                "userCheck": true
            }] 包那里拿
        }
        :return:
        """
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
                    #     {
                    #     "packageId": "5d672bfdf36fdd70472f93d933a8d679",
                    #     "packageName": "founder-demo",
                    #     "installPath": "/tmp/founder-demo",
                    #     "type": "1",
                    #     "platform": "linux",
                    #
                    #     "targetVersion": "$latest",
                    #     "cluster": None,
                    #     "preStop": True,
                    #     "postRestart": True,
                    #     "fullUpdate": False,
                    #     "autoStart": True,
                    #     "userCheck": True
                    # }
                ]
            }

            cluster_host_info_all = copy.deepcopy(self.cluster_host_info)  # 集群主机信息
            cluster_info = cluster_host_info_all.get('deviceList')[0]  # 主机列表

            # 集群信息
            cluster_name = cluster_host_info_all.get('name')
            cluster_type = cluster_host_info_all.get('type')
            cluster_instanceId = cluster_host_info_all.get('instanceId')

            # 主机信息
            host_name = cluster_info.get('hostname')
            host_instanceId = cluster_info.get('instanceId')
            host_ip = cluster_info.get('ip')

            inser_data = {
                "name": host_name,
                "instanceId": host_instanceId,
                "targetId": host_ip,
                "targetName": host_ip,
                "cluster": {
                    "clusterId": cluster_instanceId,
                    "type": cluster_type,
                    "name": cluster_name
                }
            }

            pars['targetList'].append(inser_data)
            logging.info('create_one targetList is %s' % pars.get('targetList'))

            app_info = copy.deepcopy(self.app_info)
            pars['app'] = app_info
            logging.info('create_one app info is %s' % pars.get('app'))

            pack_data = {
                "targetVersion": "$latest",
                "cluster": None,
                "preStop": True,
                "postRestart": True,
                "fullUpdate": False,
                "autoStart": True,
                "userCheck": True
            }
            package_info = copy.deepcopy(self.package_info)
            package_info.update(**pack_data)
            pars['packageList'] = [package_info]
            logging.info('create_one packageList info  is %s' % pars['packageList'])

            pars['name'] = str('灰度1台机器部署')

            logging.info('create_one name  is %s' % pars['name'])

            ret = self.http_post('post_page', '/deployStrategy', deploy_headers, deploy_host, pars)

            logging.info('create_one ret  is %s' % ret)
        except Exception as e:
            logging.error('error create_one fiald %s' % e)

    def create_other(self):
        """
        创建其他灰度策略
        :return:
        """
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
                    #     {
                    #     "packageId": "5d672bfdf36fdd70472f93d933a8d679",
                    #     "packageName": "founder-demo",
                    #     "installPath": "/tmp/founder-demo",
                    #     "type": "1",
                    #     "platform": "linux",
                    #
                    #     "targetVersion": "$latest",
                    #     "cluster": None,
                    #     "preStop": True,
                    #     "postRestart": True,
                    #     "fullUpdate": False,
                    #     "autoStart": True,
                    #     "userCheck": True
                    # }
                ]
            }

            cluster_host_info_all = copy.deepcopy(self.cluster_host_info)  # 集群主机信息
            host_info = cluster_host_info_all.get('deviceList')  # 主机列表

            # 主机信息，list
            if len(host_info) == 1:
                host_info = host_info
            elif len(host_info) > 1:
                host_info = host_info[1:]

            # 集群信息
            clusterId = cluster_host_info_all.get('instanceId')
            name = cluster_host_info_all.get('name')
            type = cluster_host_info_all.get('type')

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
                            "name": name,
                            "type": type
                        }
                    }
                )

            pars['targetList'] = targetinfo
            logging.info('create_other targetList is %s' % pars.get('targetList'))

            app_info = copy.deepcopy(self.app_info)
            pars['app'] = app_info
            logging.info('create_other app info is %s' % pars.get('app'))

            pack_data = {
                "targetVersion": "$latest",
                "cluster": None,
                "preStop": True,
                "postRestart": True,
                "fullUpdate": False,
                "autoStart": True,
                "userCheck": True
            }
            package_info = copy.deepcopy(self.package_info)
            package_info.update(**pack_data)
            pars['packageList'] = [package_info]
            logging.info('create_other packageList info  is %s' % pars['packageList'])

            pars['name'] = str('灰度其他机器部署')

            logging.info('create_other name  is %s' % pars['name'])

            ret = self.http_post('post_page', '/deployStrategy', deploy_headers, deploy_host, pars)

            logging.info('create_other ret  is %s' % ret)

        except Exception as e:
            logging.error('error create_other fiald %s' % e)

    def run(self):
        try:
            self.app_info = self.get_app_info()
            self.cluster_host_info = self.get_cluster_host_info()
            self.package_info = self.get_package_info()
            self.strategy_info = self.get_strategy_info()
        except Exception as e:
            logging.error('error %s' % e)
            logging.error('app name is', app_name)


if __name__ == '__main__':
    CreatePackageInfo()
