# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 初始化程序包安装用户和启动命令.py
@time: 2020/12/10 16:24
@desc: 程序包初始化，自动填写启动用户名，启动脚本，停止脚本
'''

import requests, logging, json, copy
import datetime

headers = {
    "org": str(EASYOPS_ORG),
    "user": "easyops",
    "host": "deployrepo.easyops-only.com",

}
cmdb_headers = {
    "org": str(EASYOPS_ORG),
    "user": "easyops",
    "host": 'cmdb_resource.easyops-only.com',
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')


class EasyopsPubic(object):

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params={}, headers=None):
        if not params.has_key('page_size'):
            page_size = 300
            params['page_size'] = page_size

        url = u'http://{easy_host}{restful_api}'.format(easy_host=EASYOPS_CMDB_HOST, restful_api=restful_api)
        logging.info('http url is %s' % url)

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
                                restful_api=url,
                                params=params,
                                method='post_page')
                            ret['list'] += temp_ret['list']
                    return ret
            except Exception as e:
                print e
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
                                restful_api=url,
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


class GetAppInfo(EasyopsPubic):
    """
    获取包的信息
    """

    def GetALLAppInfo(self, names=None):
        ret_list = []
        params = {
            "query": {
                "init_package": {"$eq": False},
                "self_research": {"$eq": "是"},
                "name": names
            },
            "fields": {
                "name": True,
                "deploy_user": True,
                "_packageList.installPath": True,
                "_packageList.packageId": True
            },
            "only_relation_view": True,
            "only_my_instance": False,
        }
        logging.info('search all app params is %s' % params)

        appdata = self.http_post('POST', '/object/APP/instance/_search', params=params, headers=cmdb_headers)
        logging.info('search all app total is %s' % appdata['total'])
        if appdata['total'] == 0:
            logging.info('search all app not init total %s' % appdata['total'])
            return
        appdataList = appdata['list']
        for data in appdataList:
            try:
                app_name = data.get('name')
                instanceId = data.get('instanceId')
                deploy_user = data.get('deploy_user')
                packageList = data.get('_packageList')
                if len(packageList) < 0: continue
                packageId = packageList[0]['packageId']
                installPath = packageList[0]['installPath']

                info = {
                    "deploy_user": deploy_user,
                    "packageId": packageId,
                    "installPath": installPath,
                    "instanceId": instanceId,

                }
                logging.info('%s app info is %s' % (app_name, info))
                ret_list.append(info)
            except Exception as e:
                logging.info('not Package inspect app name %s' % app_name)
                continue
        return ret_list

    def run(self):
        if app_name:
            params = {
                "query": {
                    "init_package": {"$eq": False},
                    "self_research": {"$eq": "是"},
                    "name": {"$eq": app_name}
                },
                "fields": {
                    "name": True,
                },
                "only_relation_view": True,
                "only_my_instance": False,
            }
        else:
            params = {
                "query": {
                    "init_package": {"$eq": False},
                    "self_research": {"$eq": "是"},
                },
                "fields": {
                    "name": True,
                },
                "only_relation_view": True,
                "only_my_instance": False,
            }

        appdata = self.http_post('POST', '/object/APP/instance/_search', params=params, headers=cmdb_headers)

        dataList = appdata['list']
        if not dataList:
            logging.warn('No program report needs to be initialized')

        for app in dataList:
            names = app.get('name')
            if not names:
                continue
            ret_list = self.GetALLAppInfo(names)

            if not ret_list:
                logging.info('app all info ret len is 0')
                continue
            logging.info('app all info ret len is %s' % len(ret_list))

            initobj = PackageInit()

            if len(ret_list) == 0:
                continue
            else:
                ret = ret_list[0]

            try:
                initobj.run(ret)
                print '-----------------------切割线-------------------------'
            except Exception as e:
                continue


class PackageInit(EasyopsPubic):
    """
    初始化程序包，创建填写运行用户和启停命令
    """

    def run(self, data):
        self.packge_id = data.get('packageId')
        self.deploy_user = data.get('deploy_user')
        self.installPath = data.get('installPath')
        self.installPath = data.get('installPath')
        self.instanceId = data.get('instanceId')
        clear_info = self.clear_info()
        if clear_info:
            update_file = self.update_file()
        else:
            update_file = False

        if update_file:
            self.register_version()

    def clear_info(self):
        """
        清理工作区，必须要清理，不然会报错，暂时不知道什么原因
        :return:
        """
        # 需要init 工作区
        init_url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_CMDB_HOST,
                                                                           PACKAGE_ID=self.packge_id)
        logging.info('init PACKAGE url is :%s' % init_url)
        response = requests.request("PUT", init_url, headers=headers)
        logging.info('init PACKAGE work area response is %s' % response.content)

        try:
            logging.info('clear info start.....')
            logging.info('clear info app instanceId..... %s' % (self.instanceId))
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_DEPLOY_REPO_HOST,
                                                                          PACKAGE_ID=self.packge_id)
            logging.info('clear url is %s' % url)
            resp = requests.delete(url=url, headers=headers, timeout=300)
            print resp.content

            status_code = resp.status_code
            if status_code == 200:
                resp_format = resp.json()
                if resp_format.get('code', None) == 0:
                    data = resp_format['data']
                    logging.info('clear data is %s' % data)
                    logging.info('clear data.....success')
                    return True
            else:
                logging.error('clear data.....filed')
                return False
        except Exception as e:
            logging.error('clear_info error %s' % e)
            logging.error('clear data.....filed')
            return False

    def update_file(self):
        """
        上传文件到工作台
        :param packge_id:
        :return:
        """
        try:

            logging.info('update_file start.....')
            logging.info('update_file app instanceId.....%s' % self.instanceId)
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}/upload'.format(
                DEPLOY_REPO_IP=EASYOPS_DEPLOY_REPO_HOST,
                PACKAGE_ID=self.packge_id)

            with open('./package.conf.yaml', 'wb') as f:
                f.write("""---
start_script: $installPath/bin/start.sh
stop_script: $installPath/bin/stop.sh
user: "%s"
...
""" % self.deploy_user)

            fps = {'file': open('./package.conf.yaml', 'rb')}
            logging.info('update_file fps..... %s' % fps)
            path_file = '/'
            params_dict = {
                'path': path_file,
                'decompress': 'true',
                'strip': 'true',
            }

            resp = requests.post(url=url, files=fps, data=params_dict, headers=headers, timeout=300)
            print resp.content

            logging.info('update_file resp..... %s' % resp)
            if resp.status_code == 200:
                resp_format = resp.json()
                if resp_format.get('code', None) == 0:
                    logging.info('update_file resp.content..... %s' % resp.content)
                    logging.info('uupdate_file.....success')
                    return True
            else:
                logging.error('uupdate_file.....filed')
                return False
        except Exception as e:
            logging.error('update_file error %s' % e)
            logging.error('ruupdate_file.....filed')
            return False

    def register_version(self):
        """
        注册初始化包
        :return:
        """
        try:
            logging.info('register_version start.....')
            url = 'http://{DEPLOY_REPO_IP}/v2/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_DEPLOY_REPO_HOST,
                                                                             PACKAGE_ID=self.packge_id)

            logging.info('register_version url..... %s' % url)
            logging.info('register_version app instanceId %s..... %s' % (url, self.instanceId))
            pkg_version = str(datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S')) + '_INIT'

            params_dict = {
                'name': str(pkg_version),
                'message': '初始化启动，停止命令等信息',
                'env_type': env_types  # 版本类型 测试
            }
            # logging.info('register_version params_dict..... %s' % params_dict)

            resp = requests.post(url=url, json=params_dict, headers=headers, timeout=30)
            resp_format = resp.json()
            logging.info('register_version resp_data..... %s' % resp_format['data'])
            print resp_format['error']
            if resp_format['data'] or (resp_format['error'] == u'提交文件无变更'):
                # 修改模型属性为True
                params = {
                    "init_package": True
                }
                put_url = '/v2/object/APP/instance/' + self.instanceId
                logging.info('update app url..... %s' % put_url)
                ret = self.http_post('put', put_url, headers=cmdb_headers, params=params)
                logging.info('register_version.....success')
            else:
                logging.error('register_version.....filed')
        except Exception as e:
            logging.error('register_version error %s' % str(e))
            logging.error('register_version.....filed')


if __name__ == '__main__':
    obj = GetAppInfo()
    obj.run()
