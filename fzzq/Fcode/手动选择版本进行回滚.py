# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 输入版本号，进行回滚.py
@time: 2020/12/11 11:42
@desc: 手动输入版本号，进行版本回滚
'''
import requests, json, logging, sys

easyops_org = '3087'
cmdb_host = '28.163.0.123'

easyops_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                   'content-Type': 'application/json'}

# APP_NAME = 'secured_ifc-index-dubbo-service'
# version = '1.5'

# 0开发， 1 测试
clusterType = '1'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')


class EasyopsPubic(object):

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, headers=easyops_headers, cmdb_host=cmdb_host, params={}):
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


class GetVersionInfo(EasyopsPubic):

    def DeployInfo(self):
        params = {
            "query": {
                "name": {"$eq": APP_NAME},

            },
            "fields": {
                "instanceId": True
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
            url = "http://" + cmdb_host + ":8061/deployStrategy?appId=" + AppInstanceId
            logging.info('search deployStrategy url is  %s' % data)

            payload = {}
            headers = {
                'host': 'deploy.easyops-only.com',
                'org': easyops_org,
                'user': 'defaultUser',
                'content-Type': 'application/json',
            }

            response = requests.request("GET", url, headers=headers, data=payload)
            data_list = json.loads(response.text.encode('utf8')).get('data')
            for data in data_list:
                cluster_type = str(data.get('clusterType'))
                if cluster_type == clusterType:
                    name = data.get('name')
                    id = data.get('id')
                    logging.info('name %s id %s' % (name, id))
                    if u'全量部署' == name:
                        PutStr("all_id", id)
                    elif u'灰度1台机器部署' == name:
                        PutStr("one_id", id)
                    elif u'灰度其他机器部署' == name:
                        PutStr("other_id", id)
        except Exception as e:
            raise Exception('先创建部署策略')

    def GetAllVersion(self):
        search_name = version + "@" + APP_NAME

        params = {
            "query": {
                "name": {"$eq": search_name},

            },
            "fields": {
                # "pkgId": True,
                "versionId": True

            },
            "only_relation_view": True,
            "only_my_instance": False,
            "page_size": 1
        }
        logging.info('search params is %s' % params)
        ret = self.http_post('post', '/object/GQPACAGE_VERSION_UAT/instance/_search', params=params)
        if ret.get('total', False):
            versionId = ret['list'][0]['versionId']
            logging.info('search ret is %s' % ret)
            logging.info('search versionId ret is %s' % versionId)
            return versionId

        logging.info('search version ret is None')

    def CheckVersion(self):
        """
        根据输入的版本，校验版本是否正确
        :return:
        """
        versionId = self.GetAllVersion()
        if not versionId:
            logging.info('%s is not version %s' % (APP_NAME, version))
            sys.exit(1)

        # 获取部署策略ID
        self.DeployInfo()

        PutStr("versionId", versionId)  # 版本ID
        PutStr("version", version)  # 版本号


if __name__ == '__main__':
    obj = GetVersionInfo()
    obj.CheckVersion()
