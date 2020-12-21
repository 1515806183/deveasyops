# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: search_packet.py
@time: 2020/12/15 13:57
@desc: 搜索程序包，判断是否在平台能注册  通过version和commitID
'''

import requests, json, logging, sys

easyops_org = '3087'
cmdb_host = '28.163.0.123'

easyops_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                   'content-Type': 'application/json'}

# 0开发， 1 测试， 2生产
clusterType = '0'
pageke_env_type = '1'  # 1为开发，3为测试，15为生产，程序包版本

#version = '4.0.25'  # 程序包版本
#application = 'secured_ifc-index-dubbo-service'  # 应用名
#commitId = 'assaaa'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')


class EasyopsPubic(object):

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, headers=easyops_headers, cmdb_host=cmdb_host, params={}):

        url = u'http://{easy_host}{restful_api}'.format(easy_host=cmdb_host, restful_api=restful_api)
        if method in ('post', 'POST'):
            page_size = 100
            if not params.has_key('page_size'):
                params['page_size'] = page_size

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

        # get翻页查询，依赖http_post
        elif method in ('get_page',):
            try:
                r = requests.get(url, headers=headers, timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}


class SearchAppPackage(EasyopsPubic):
    """
    根据应用名称，和cmooit，在程序包里搜，是否有程序包
    """

    def serach_package(self):
        params = {
            "query": {
                "name": {"$eq": application},

            },
            "fields": {
                "instanceId": True,
                "_packageList": True
            },
            "only_relation_view": True,
            "only_my_instance": False,
            "page_size": 1
        }

        logging.info('search APP params is  %s' % params)
        try:
            data = self.http_post('post', '/object/APP/instance/_search', params=params)
            logging.info('search APP ret is  %s' % data)
            AppInstanceId = data['list'][0]['instanceId']
            packageList = data['list'][0]['_packageList']
            logging.info('search APP packageList is  %s' % packageList)
            if len(packageList) == 0:
                raise Exception('该应用没有程序包')
            packageId = packageList[0]['packageId']
            logging.info('search APP packageId is  %s' % packageId)

            # 根据packageId 获取所有的程序包
            packageId_headers = {'host': 'deploy.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                                 'content-Type': 'application/json'}
            logging.info('search APP hearder is  %s' % packageId_headers)
            payload = {}
            version_result = []
            version_page = 1
            while True:
                url = "http://{host}/version/list?packageId={packageId}&page={page}&pageSize=300".format(
                    packageId=packageId, page=version_page, host=cmdb_host)
                response = requests.request("GET", url, headers=packageId_headers, data=payload)
                result = response.json()
                if result['data']['list'] and len(result['data']['list']) > 0:
                    data_list = result['data']['list']
                    version_result = version_result + data_list
                    version_page += 1
                else:
                    break

            for data in version_result:
                name = data.get('name')  # 程序包名称
                env_type = data.get('env_type')  # 运行环境。3 测试
                if (name == version) and (env_type == pageke_env_type): # 如果版本相同， 环境相同则有这个包
                    versionId = data.get('versionId')  # 程序包版本
                    logging.info('search package name is  %s' % name)
                    logging.info('search package env_type is  %s' % env_type)
                    logging.info('search package versionId is  %s' % versionId)
                    PutStr("packageret", u"True")
                    PutStr("version", version)
                    return versionId

        except Exception as e:
            raise Exception('获取应用没有程序包出错')


if __name__ == '__main__':
    SearchAppPackage().serach_package()
