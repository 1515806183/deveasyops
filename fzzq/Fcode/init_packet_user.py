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

EASYOPS_CMDB_HOST = '28.163.0.123:80'

headers = {
    "org": '3087',
    "user": "easyops",
    "host": "deployrepo.easyops-only.com"

}
cmdb_headers = {
    "org": '3087',
    "user": "easyops",
    "host": 'cmdb_resource.easyops-only.com'
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

    def GetALLAppInfo(self):
        ret_list = []
        params = {
            "query": {
                "init_package": {"$eq": False},
                "self_research": {"$eq": "是"}
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
                name = data.get('name')
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
                logging.info('%s app info is %s' % (name, info))
                ret_list.append(info)
            except Exception as e:
                logging.info('not Package inspect app name %s' % name)
                continue
        return ret_list

    def run(self):
        ret_list = self.GetALLAppInfo()

        if not ret_list:
            logging.info('app all info ret len is 0')
            return
        logging.info('app all info ret len is %s' % len(ret_list))

        initobj = PackageInit()

        for ret in ret_list:
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
        self.clear_info()
        self.update_file()
        self.register_version()

    def clear_info(self):
        """
        清理工作区，必须要清理，不然会报错，暂时不知道什么原因
        :return:
        """
        try:
            logging.info('clear info start.....')
            logging.info('clear info app instanceId..... %s' % (self.instanceId))
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_CMDB_HOST,
                                                                          PACKAGE_ID=self.packge_id)
            logging.info('clear url is %s' % url)
            resp = requests.delete(url=url, headers=headers, timeout=300)

            status_code = resp.status_code
            if status_code == 200:
                resp_format = resp.json()
                if resp_format.get('code', None) == 0:
                    data = resp_format['data']
                    logging.info('clear data is %s' % data)
        except Exception as e:
            logging.ERROR('clear_info ERROR %s' % e)

    def update_file(self):
        """
        上传文件到工作台
        :param packge_id:
        :return:
        """
        try:

            logging.info('update_file start.....')
            logging.info('update_file app instanceId.....%s' % self.instanceId)
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}/upload'.format(DEPLOY_REPO_IP=EASYOPS_CMDB_HOST,
                                                                                 PACKAGE_ID=self.packge_id)

            with open('./package.conf.yaml', 'wb+') as f:
                f.write(
                    """
---
proc_list: []
port_list: []
proc_guard: ~
port_guard: ~
start_script: "$installPath/bin/start.sh"
stop_script: "$installPath/bin/stop.sh"
monitor_script: ""
user: "%s"
restart_script: ""
install_prescript: ""
install_postscript: ""
update_prescript: ""
update_postscript: ""
rollback_prescript: ""
rollback_postscript: ""
user_pre_check: ""
user_check_script: ""
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

            logging.info('update_file resp..... %s' % resp)
            if resp.status_code == 200:
                resp_format = resp.json()
                if resp_format.get('code', None) == 0:
                    logging.info('update_file resp.content..... %s' % resp.content)
        except Exception as e:
            logging.ERROR('update_file ERROR %s' % e)

    def register_version(self):
        """
        注册初始化包
        :return:
        """
        try:
            logging.info('register_version start.....')
            url = 'http://{DEPLOY_REPO_IP}/v2/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_CMDB_HOST,
                                                                             PACKAGE_ID=self.packge_id)

            logging.info('register_version url..... %s' % url)
            logging.info('register_version app instanceId %s..... %s' % (url, self.instanceId))
            pkg_version = 0.0001

            params_dict = {
                'name': str(pkg_version),
                'message': '初始化启动，停止命令等信息',
                'env_type': 3  # 版本类型 测试
            }
            # logging.info('register_version params_dict..... %s' % params_dict)

            resp = requests.post(url=url, json=params_dict, headers=headers, timeout=30)
            resp_format = resp.json()
            logging.info('register_version resp_data..... %s' % resp_format['data'])

            if resp_format['data']:
                # 修改模型属性为True
                params = {
                    "init_package": True
                }
                put_url = '/v2/object/APP/instance/' + self.instanceId
                logging.info('update app url..... %s' % put_url)
                ret = self.http_post('put', put_url, headers=cmdb_headers, params=params)

        except Exception as e:
            logging.ERROR('register_version ERROR %s' % str(e))


if __name__ == '__main__':
    obj = GetAppInfo()
    obj.run()
