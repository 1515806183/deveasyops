# coding:utf-8
import datetime
import json
from wsgiref.simple_server import make_server
import requests
import logging
import os
import time
import copy, sys

reload(sys)
sys.setdefaultencoding('utf8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

cmdb_headers = {
    "content-Type": "application/json",
    "host": "cmdb_resource.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

# 搜索程序包headers
deploy_headers = {
    "content-Type": "application/json",
    "host": "deploy.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

deployrepo_headers = {
    # "org": str(EASYOPS_ORG),
    "org": '3087',
    "user": "easyops",
    "host": "deployrepo.easyops-only.com",

}

tool_headers = {
    "content-Type": "application/json",
    "host": "tool.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

easyopsHost = '10.163.128.232'
# easyopsHost = '28.163.0.123'
domain_name = 'cmdb.foundersc.com'
EASYOPS_DEPLOY_REPO_HOST = easyopsHost

deploy_host = easyopsHost + ':8061'
cmdb_host = easyopsHost

# 集群类型 0 开发， 1测试  2生产
clusterNumList = ["0", "1", "2"]
pro_tmp_full = u'生产环境全量部署(Fcode)'
pro_tmp_galy = u'生产环境灰度部署(Fcode)'
dev_tmp_full = u'开发环境部署(Fcode)'
uat_tmp_full = u'测试环境部署(Fcode)'

# 自动刷新权限工具
TOOLID = '4f0de6b83cea57dafbcbdfc3506f78d1'  # 工具库ID
VID = '3f9251c153a2c790d2b4ae701f9aaac4'  # 工具库版本ID


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
            except Exception as e:
                ret = json.loads(r.content)
            return ret

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
                if int(data.get('code')) == 0:
                    return r.content
                else:
                    return False
        except Exception as e:
            return False


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


# 初始化程序包
class PackageInit():
    """
    初始化程序包，创建填写运行用户和启停命令
    """

    def run(self, data, pro_type):
        self.pro_type = pro_type  # 工程类型
        self.packge_id = data.get('packageId')
        self.deploy_user = data.get('deploy_user')
        self.installPath = data.get('installPath')
        self.instanceId = data.get('instanceId')
        clear_info = self.clear_info()
        if clear_info:
            update_file = self.update_file()
        else:
            update_file = False

        if update_file:
            status = self.register_version()
            return status

    def clear_info(self):
        """
        清理工作区，必须要清理，不然会报错，暂时不知道什么原因
        :return:
        """
        # 需要init 工作区
        init_url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=easyopsHost,
                                                                           PACKAGE_ID=self.packge_id)
        logging.info('init PACKAGE url is :%s' % init_url)
        response = requests.request("PUT", init_url, headers=deployrepo_headers)
        logging.info('init PACKAGE work area response is %s' % response.content)

        try:
            logging.info('clear info start.....')
            logging.info('clear info app instanceId..... %s' % (self.instanceId))
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=EASYOPS_DEPLOY_REPO_HOST,
                                                                          PACKAGE_ID=self.packge_id)
            logging.info('clear url is %s' % url)
            resp = requests.delete(url=url, headers=deployrepo_headers, timeout=300)
            print '清理工作区: %s' % resp.content

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
            if "vue2" in self.pro_type:
                with open('./package.conf.yaml', 'wb') as f:
                    f.write("""---
start_script:
stop_script:
user: "%s"
...
""" % self.deploy_user)
            else:
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

            resp = requests.post(url=url, files=fps, data=params_dict, headers=deployrepo_headers, timeout=300)
            print '上传文件: %s' % resp.content

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
                'env_type': '15'  # 版本类型 测试
            }
            logging.info('register_version params_dict..... %s' % params_dict)

            resp = requests.post(url=url, json=params_dict, headers=deployrepo_headers, timeout=30)
            resp_format = resp.json()
            logging.info('register_version resp_data..... %s' % resp_format['data'])
            print u'注册版本: %s' % str(resp_format['error'])
            if resp_format['data'] or (resp_format['error'] == u'提交文件无变更'):
                # 修改模型属性为True,版本注册成功
                logging.info('register_version.....success')

                params = {
                    "init_package": True
                }
                put_url = 'http://{HOST}/v2/object/APP/instance/{instanceId}'.format(HOST=easyopsHost,
                                                                                     instanceId=self.instanceId)
                logging.info('update app url..... %s' % put_url)
                ret = http_post('PUT', put_url, headers=cmdb_headers, params=params)
                return True
            else:
                logging.error('register_version.....filed')
                return False
        except Exception as e:
            logging.error('register_version error %s' % str(e))
            logging.error('register_version.....filed')
            return False


# 创建程序包，初始化程序包，关联程序包
class AutoaddApplicationInformation():
    """
    自动创建应用后，所关联的信息
    """

    def __init__(self, ext_info):
        self.ext_info = ext_info
        self.instance_id = self.ext_info.get('instance_id')
        self.instance_name = self.ext_info.get('instance_name')
        self.app_info = self._get_app_info()

    # 应用加入角色组
    def addUserRole(self, UserDict):
        """
        添加用户到角色里
        # 1. 先查询角色里面的用户
        # 2. 现网角色里面的用户
        # 3. 查询用户 - 现网用户 = 删除用户
        # 4. 剔除删除的角色用户
        :param data: 用户信息，生产，开发，测试
        :return:
        """
        roldDict = {
            "tester": '5ff6d9561fc6da3b914b1e7d',
            "owner": '5ff6d9661fc6da3b914b1e7e',
            "developer": '5ff6b5431fc6da3b944b1edf',
        }

        for k, userList in UserDict.items():
            roleID = roldDict[k]
            logging.info('Person in charge information to start processing, roleID: %s, name: %s' % (roleID, k))
            self.__dealUserInfo(roleID, userList)

    # 处理需要添加和删除的应用
    def __dealUserInfo(self, roleID, userList):
        logging.info('------------dealuser leader space------------')
        logging.info('user roleID is :%s' % roleID)
        url = "http://{HOST}:8085/api/v1/permission_role/config/{role}?page=1&page_size=900".format(HOST=easyopsHost,
                                                                                                    role=roleID)
        developerUserInfo = http_post('GET', url)  # 平台里面的用户信息

        logging.info('Information of the user director in the platform: %s' % developerUserInfo)

        platformUser = developerUserInfo.get('user')
        logging.info('The total number of users should be : %s' % len(platformUser))

        removeUserList = list(set(platformUser) - set(userList))
        addUserList = list(set(userList) - set(platformUser))

        logging.info('List of users to be removed : %s' % removeUserList)
        logging.info('List of users to be added : %s' % addUserList)

        # 需要移除的用户
        if removeUserList:
            ret = self.delUser(roleID, removeUserList)
            logging.info('removeUserList status: %s' % (str(ret)))
        # 增加用户
        if addUserList:
            ret = self.addUser(roleID, addUserList)
            logging.info('addUserList status: %s' % (str(ret)))

        logging.info('------------dealuser END ------------')

    # 角色删除多余的用户
    def delUser(self, roleID, removeUserList):
        """
        删除多余的用户
        :param roleID: 角色ID
        :return:
        """
        url = "http://{HOST}:8085/api/v1/permission_role/role_delete_user_or_group/{role}".format(HOST=easyopsHost,
                                                                                                  role=roleID)

        params = {
            "operate_user": removeUserList,
            "operate_user_group": []

        }
        ret = http_post('PUT', url, params=params)
        return ret

    # 角色添加用户
    def addUser(self, roleID, addUserList):
        """
        增加的用户
        :param roleID: 角色ID
        :return:
        """
        url = "http://{HOST}:8085/api/v1/permission_role/role_add_user/{role}".format(HOST=easyopsHost, role=roleID)
        params = {
            "operate_user": addUserList,
        }
        ret = http_post('PUT', url, params=params)
        return ret

    # 根据应用名称查询程序包信息
    def __serch_package(self, app_name):
        url = 'http://{HOST}/package/search?name={appname}&page=1&pageSize=10&exact=true'.format(HOST=easyopsHost,
                                                                                                 appname=app_name)
        logging.info(u'根据应用名称查询程序包URL: %s' % url)
        ret = http_post('GET', url, headers=deploy_headers)
        return ret

    # 创建修改程序包信息
    def createUpdatePackage(self):

        diff_data = self.ext_info.get('diff_data', {})
        platform_type = self.app_info[0].get('platform_type', '')
        install_path = self.app_info[0].get('install_path', '')
        deploy_user = self.app_info[0].get('deploy_user', '')
        self.app_instanceId = self.app_info[0].get('instanceId')

        if diff_data.has_key("name"):
            logging.info(u'应用更新的字段为:%s' % self._change_fields)
            diff_data_name = diff_data.get('name')
            new_name = diff_data_name.get('new')  # 新应用名称
            old_name = diff_data_name.get('old')  # 新应用名称
            logging.info(u'更新了应用名称，新应用名称为: %s' % new_name)
            logging.info(u'开始查询旧程序包信息，旧程序包名称为:%s' % old_name)
            ret = self.__serch_package(old_name)
            logging.info(u'查询程序包数量为： %s' % ret.get('total'))  # 这里程序包是存在的（必须）

            packageId = ret.get('list')[0].get('packageId')
            logging.info('查询的程序包ID为:%s' % packageId)
            url = u"http://{host}/package/{packageId}".format(host=easyopsHost, packageId=packageId)

            params = {"name": new_name}
            # 1. 创建应用，程序包以前存在,修改包信息
            if diff_data.has_key('platform_type') or diff_data.has_key('install_path'):
                logging.info('Updated data : %s' % diff_data)
                if diff_data.has_key('platform_type'):
                    new_platform_type = diff_data.get('platform_type').get('new').lower()
                    params['platform'] = new_platform_type
                if diff_data.has_key('install_path'):
                    new_install_path = diff_data.get('install_path').get('new')
                    params['installPath'] = new_install_path

            ret = http_post('PUT', url, params, deploy_headers)
            logging.info(u'更新程序包名称返回结果:%s' % ret)

        else:
            packageId = ''
            # 1. 先从程序包中查询程序包是否存在
            ret = self.__serch_package(self.instance_name)
            # {u'total': 0, u'list': [], u'page': 1, u'pageSize': 10}

            if not platform_type or not install_path or not deploy_user:
                logging.error('Application has no deployment path, deployment user, platform type')
                return False

            if str(ret.get('total')) == '0':
                # 包不存在，创建包
                logging.info('Query package information : %s' % ret)
                # 需要创建程序包

                url = u"http://{host}/package".format(host=easyopsHost)
                logging.info('Create package URL: %s' % url)
                params = {
                    "name": self.instance_name,
                    "cId": 1,
                    "type": 1,
                    "installPath": install_path,
                    "platform": platform_type.lower(),
                    "memo": "auto create"
                }
                logging.info('Create package params: %s' % params)
                ret = http_post('POST', url, params, headers=deploy_headers)
                logging.info('Create package and return result : %s' % ret)
                if ret.get('code') == 0:
                    packageId = ret.get('data')['packageId']

            else:
                # {u'total': 1, u'list': [{u'category': u'', u'style': u'', u'lastVersionInfo': {}, u'name': u'111', u'conf': None, u'cId': u'1', u'memo': u'auto create', u'creator': u'defaultUser', u'ctime': u'2021-01-11 16:18:55', u'repoPath': u'/3087/51/67/69/aba9c50cd9a5c05068929d1649', u'source': u'', u'instanceCount': 0, u'installPath': u'/rooot/1', u'platform': u'Linux', u'packageId': u'516769aba9c50cd9a5c05068929d1649', u'mtime': None, u'org': u'3087', u'authUsers': None, u'type': u'1', u'repoId': u'', u'icon': u''}], u'page': 1, u'pageSize': 10}
                # 包存在，比较包的部署路径，类型，如果不相同则修改包信息
                # 只能从self.exce_info获取变更的信息，不然数据不会变 install_path
                packageId = ret.get('list')[0].get('packageId')
                logging.info(u'程序包存在，下面判断包路径和用户是否修改, 应用名称是否修改')
                params = {}

                # 1. 创建应用，程序包以前存在,修改包信息
                if diff_data.has_key('platform_type') or diff_data.has_key('install_path'):
                    logging.info('Updated data : %s' % diff_data)
                    if diff_data.has_key('platform_type'):
                        new_platform_type = diff_data.get('platform_type').get('new').lower()
                        params['platform'] = new_platform_type
                    if diff_data.has_key('install_path'):
                        new_install_path = diff_data.get('install_path').get('new')
                        params['installPath'] = new_install_path

                if params:
                    logging.info(u'更新程序包信息为 : %s' % params)
                    url = u"http://{host}/package/{packageId}".format(host=easyopsHost, packageId=packageId)
                    logging.info(u'更新程序包的URL: %s' % url)
                    ret = http_post('PUT', url, params, deploy_headers)
                    logging.info(u'更新程序包请求结果 : %s' % ret)

                    # 这里要更新下部署策略，不然程序包不会绑定最新的
                    for clusterNum in clusterNumList:
                        logging.info(
                            u'程序包部署信息已经修改，修改修改部署策略的程序包信息, 集群类型 0 开发， 1测试  2生产--------------------当前处理的集群ID：%s' % clusterNum)
                        CreateClusterInfo(self.app_instanceId, clusterNum)
                else:
                    logging.warning(u'应用名称和程序包信息没修改，无需处理')
                    return False

        ret_data = {
            "packageId": packageId,
            "deploy_user": deploy_user,
            "installPath": install_path,
            "instanceId": self.instance_id,
        }
        logging.info(u'创建或更新的程序包返回信息为: %s' % ret_data)
        return ret_data

    # 应用关联程序包
    def linkPackage(self, data):
        """
        应用关联程序包
        :return:
        """
        try:
            falg = True
            logging.info(u'包信息: %s' % data)
            logging.info(u'应用信息: %s' % self.app_info)
            packageId = data.get('packageId')
            installPath = data.get('installPath')
            if not packageId:
                logging.error(u'应用未关联任何包，packageId为 : %s' % packageId)

            # 判断应用是否存在此程序包
            url = 'http://{HOST}:8113/app/{appid}/package'.format(HOST=easyopsHost, appid=self.instance_id)

            # 程序包关联应用，bug问题，直接关联，[]不会覆盖其他的程序包
            params = [
                {
                    "installPath": installPath,
                    "packageId": packageId
                }
            ]

            if not self.app_info[0].has_key('_packageList'):
                logging.warning(u'应用没有程序包，需要创建程序包')

            else:
                logging.info(u'应用系统中有软件包')
                # 1.根据packageId 判断是否存在，如果存在判断部署路径是否相同
                _packageList = self.app_info[0].get('_packageList')
                for package in _packageList:
                    # 比较现网程序包信息和应用里面的信息是否相同。
                    app_packageId = package.get('packageId')
                    app_installPath = package.get('installPath')
                    logging.info('应用信息里面的程序包安装路径 %s, %s' % (app_packageId, app_installPath))
                    logging.info('程序包里面的安装路径 %s, %s' % (packageId, installPath))

                    # 程序包ID都不相同，删除程序包 程序包路径不相同,删除程序包
                    if (packageId != package.get('packageId')) or (
                            (packageId == package.get('packageId')) and (installPath != package.get('installPath'))):
                        del_url = 'http://{HOST}:8113/app/{appid}/package/{packId}'.format(HOST=easyopsHost,
                                                                                           appid=self.instance_id,
                                                                                           packId=app_packageId)
                        ret = http_post('delete', url=del_url)
                        logging.warning(
                            'The deployment path is not the same. Delete the package and re establish the relationship with the application system')
                        logging.info(ret)
                        continue
                    if (packageId == package.get('packageId')) and (installPath == package.get('installPath')):
                        falg = False

            # 如果程序包路径和id相同的话，则无需修改和应用的关系，如果修改api会报错
            if falg:
                logging.info('Associate package parameters : %s, url : %s' % (params, url))
                ret = http_post('POST', url, params)  # {"code":0,"codeExplain":"","error":"","data":{}}
                logging.info(ret)
                if str(ret.get('code')) != '0':
                    logging.error('Application associated package filed')
                logging.info('Application associated package ret :%s' % ret)

                # 如果为真，则需要修改部署策略的程序包信息
                logging.info('程序包已经变更，现在需要变更部署策略里面的程序包信息')
                for clusterNum in clusterNumList:
                    logging.info(u'---处理部署策略的群集ID为: %s, 集群类型 0 开发， 1测试  2生产' % clusterNum)
                    CreateClusterInfo(self.instance_id, clusterNum)
                logging.info('变更部署策略里面的程序包信息完成')
            else:
                logging.warning('程序包和应用名称没修改,不会修改应用和程序包信息')

        except Exception as e:
            logging.error('Application Association Package error: %s' % e)

    # 初始化程序包第一个版本
    def initPackage(self, data):
        logging.info('Initialize package parameters: %s, pro_type: %s' % (data, self.pro_type))
        status = PackageInit().run(data, self.pro_type)
        return status

    # 获取应用信息
    def _get_app_info(self):
        # 查询应用
        url = "http://{host}/object/{model}/instance/_search".format(host=easyopsHost, model='APP')
        search_parse = {
            "query": {
                "instanceId": {
                    "$eq": self.instance_id
                }
            },
            "fields": {
                "name": True,
                "self_research": True,
                "platform_type": True,
                "install_path": True,
                "init_package": True,
                "deploy_user": True,
                "_packageList": True,
                "init_tem": True,
                "__pipeline": True,
                "type": True  # 工程类型
            }
        }
        app_ret = http_post('POST', url, params=search_parse)
        self.app_info = copy.deepcopy(app_ret)
        return self.app_info

    # 获取流水线模板
    def _get_line_tmp(self, app_name, app_instanceId):
        logging.info('------------------------------------------------------------获取流水线模板')
        url = "http://{HOST}/flows?page=1&pageSize=500&category=pipeline_template".format(HOST=easyopsHost)
        logging.info('search tmp url :%s' % url)
        ret = http_post('GET', url, headers=tool_headers)
        tmp_list = ret.get('list')

        tmp_datas = {
            pro_tmp_full: {},
            pro_tmp_galy: {},
            dev_tmp_full: {},
            uat_tmp_full: {}
        }

        tmp_id = {
            pro_tmp_full: '',
            pro_tmp_galy: '',
            dev_tmp_full: '',
            uat_tmp_full: ''
        }

        tmp_versin = {
            pro_tmp_full: '',
            pro_tmp_galy: '',
            dev_tmp_full: '',
            uat_tmp_full: ''
        }

        # test, production development
        env_type = {
            pro_tmp_full: 'production',
            pro_tmp_galy: 'production',
            dev_tmp_full: 'development',
            uat_tmp_full: 'test'
        }

        # 需要跟应用关联的pipline
        focde_list = []
        for tmp in tmp_list:
            name = tmp.get('name')
            if name == pro_tmp_full:
                metadata = tmp['metadata']
                metadata.update({"appId": app_instanceId})
                tmp['name'] = app_name + '-' + name
                tmp_datas[pro_tmp_full]['category'] = 'app_pipeline'
                tmp_datas[pro_tmp_full]['metadata'] = metadata
                tmp_datas[pro_tmp_full]['name'] = tmp['name']
                tmp_datas[pro_tmp_full]['stepList'] = tmp['stepList']
                tmp_datas[pro_tmp_full]['flowOutputs'] = tmp['flowOutputs']
                tmp_id[pro_tmp_full] = tmp['flowId']
                tmp_versin[pro_tmp_full] = tmp['version']

            elif name == pro_tmp_galy:
                metadata = tmp['metadata']
                metadata.update({"appId": app_instanceId})
                tmp['name'] = app_name + '-' + name
                tmp_datas[pro_tmp_galy]['category'] = 'app_pipeline'
                tmp_datas[pro_tmp_galy]['metadata'] = metadata
                tmp_datas[pro_tmp_galy]['name'] = tmp['name']
                tmp_datas[pro_tmp_galy]['stepList'] = tmp['stepList']
                tmp_datas[pro_tmp_galy]['flowOutputs'] = tmp['flowOutputs']
                tmp_id[pro_tmp_galy] = tmp['flowId']
                tmp_versin[pro_tmp_galy] = tmp['version']

            elif name == dev_tmp_full:
                metadata = tmp['metadata']
                metadata.update({"appId": app_instanceId})
                tmp['name'] = app_name + '-' + name
                tmp_datas[dev_tmp_full]['category'] = 'app_pipeline'
                tmp_datas[dev_tmp_full]['metadata'] = metadata
                tmp_datas[dev_tmp_full]['name'] = tmp['name']
                tmp_datas[dev_tmp_full]['stepList'] = tmp['stepList']
                tmp_datas[dev_tmp_full]['flowOutputs'] = tmp['flowOutputs']
                tmp_id[dev_tmp_full] = tmp['flowId']
                tmp_versin[dev_tmp_full] = tmp['version']

            elif name == uat_tmp_full:
                metadata = tmp['metadata']
                metadata.update({"appId": app_instanceId})
                tmp['name'] = app_name + '-' + name
                tmp_datas[uat_tmp_full]['category'] = 'app_pipeline'
                tmp_datas[uat_tmp_full]['metadata'] = metadata
                tmp_datas[uat_tmp_full]['name'] = tmp['name']
                tmp_datas[uat_tmp_full]['stepList'] = tmp['stepList']
                tmp_datas[uat_tmp_full]['flowOutputs'] = tmp['flowOutputs']
                tmp_id[uat_tmp_full] = tmp['flowId']
                tmp_versin[uat_tmp_full] = tmp['version']

        # print json.dumps(tmp_datas['Fcode_Gray_Flow'])
        for k, tmp in tmp_datas.items():
            # 创建测试流程
            try:
                url = 'http://{HOST}/flows'.format(HOST=easyopsHost)
                ret = requests.request("POST", url, headers=tool_headers, data=json.dumps(tmp_datas[k]))
                ret = json.loads(ret.text.encode('utf8'))
                logging.warning(str(ret.get('error')))
                data = ret.get('data')
                flowId = data.get('flowId')  # 流程ID
                # version = data.get('version')

                data = {"flowId": flowId,
                        "metadata": json.dumps({"type": env_type[k], "appId": app_instanceId}),
                        "name": k, "templateId": tmp_id[k],
                        "templateVersion": tmp_versin[k]}
                focde_list.append(data)

            except Exception as e:
                logging.error('获取流水线模板报错:%s' % e)
        return focde_list

    # 创建流水线
    def create_pipline(self):
        app_name = self.app_info[0].get('name')
        app_instanceId = self.app_info[0].get('instanceId')
        __pipeline = self.app_info[0].get('__pipeline', [])

        focde_list = self._get_line_tmp(app_name, app_instanceId)

        __pipeline += focde_list
        logging.info('应用开始关联流水线，pipline数量:%s' % len(__pipeline))
        # 获取流水线模板信息Fcode_Full_Flow， Fcode_Gray_Flow
        url = 'http://{HOST}/object/APP/instance/{ID}'.format(HOST=easyopsHost, ID=app_instanceId)
        params = {
            "__pipeline": __pipeline,
            "init_tem": True
        }
        ret = requests.request("PUT", url, headers=cmdb_headers, data=json.dumps(params))
        logging.info('Update pipeline initialization template state: %s' % ret)

    def run(self, data):
        if not self.app_info:
            logging.error('Failed to query application information')
            return

        self.pro_type = self.app_info[0].get('type', '')  # 工程类型 vue2 不需要启停脚本
        self.init_package = self.app_info[0].get('init_package')  # 是否已经初始化程序包 true false
        self._change_fields = self.ext_info.get('_change_fields', '')  # [u'name'] 修改字段

        # 只处理自研应用的初始化
        if self.app_info[0].get('self_research') != u"是":
            logging.warning('Only the initialization of self-developed application is processed')
            return
        event = data.get('event')  # event.instance.create event.instance.modify
        logging.info('event info %s' % event)

        # 程序创建程序包，只有新建应用，修改了应用名称，部署路径，平台类型才会触发
        diff_data = self.ext_info.get('diff_data', {})
        logging.info(u'应用修改的字段为:%s' % diff_data)
        diff_set = set(diff_data.keys())
        package_set = set(["name", "install_path", "platform_type"])

        if event in ['event.instance.create', ] or (diff_set & package_set):
            logging.info('------------------------------------------------------------创建程序包')
            packageData = self.createUpdatePackage()  # 创建修改程序包,返回程序包ID
            logging.info('程序包创建修改代码运行完成。。')
            if packageData:
                logging.info('程序包数据信息 : %s' % packageData)
                # 初始化程序包第一个版本,只初始化一次,如果修改了应用名称，则需要重新创建程序包，初始化程序包，关联程序包
                logging.info(u'判断程序包失败能初始化:%s' % self.init_package)
                # 如果init_package 为false 则初始化程序包
                if not self.init_package:
                    logging.info('------------------------------------------------------------初始化程序包')
                    status = self.initPackage(packageData)
                    logging.info('------------------------------------------------------------是否初始化程序包值: %s' % status)
                logging.info('------------------------------------------------------------应用关联程序包')
                self.linkPackage(packageData)  # 应用关联程序包

        # 创建流水线
        logging.info('------------------------------------------------------------处理流水线')
        init_tem = self.app_info[0].get('init_tem')
        if init_tem:
            logging.warning('流水线已经初始化，值为:%s' % str(init_tem))
            return
        self.create_pipline()


# 根据appid，创建修改部署策略，程序包和应用名一样
class CreateClusterInfo(EasyopsPubic):
    """
    创建部署策略
    1. 根据应用获取主机信息，只获取生产环境的
    1.1 需要主机的name，id， 对应的集群信息

    2. 获取应用信息，需要name， id
    3。 获取包信息，需要id，name
    """

    def __init__(self, app_instanceId, clusterNum):
        self.app_instanceId = app_instanceId
        self.clusterNum = clusterNum
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
                if deploy_policy.get('clusterType') == self.clusterNum:  # 判断部署策略是否对应上环境类型 开发-开发 生产-生产
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
                    "instanceId": {"$eq": self.app_instanceId},
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

            logging.info('Number of Application Clusters: %s' % len(ret['list']))
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
                if str(cluster['type']) == str(self.clusterNum):
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
            package_info = self.get_package_info(ret.get('name'))
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
    def get_package_info(self, app_name):
        """
        获取包信息
        :return:
        """
        try:
            search_url = '/package/search?page=1&pageSize=10&name={app}&exact=true'.format(app=app_name)

            logging.info('search package params info: %s' % search_url)
            logging.info('search package headers info: %s' % deploy_headers)

            ret = self.http_post('get_page', search_url, deploy_headers, cmdb_host)

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
                "clusterType": self.clusterNum,
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
                name = cluster_info.get('cluster_name')
                type = cluster_info.get('cluster_type')

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
            logging.error('APP: %s, error deploy fiald %s' % (APP_InstanceId, e))

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
        deploy_packageList = deploy_policy.get('packageList')  # list 现网数据
        package_info = data.get('package_info')  # dict

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

        # 处理程序包信息
        for package in deploy_packageList:
            packageId = package.get('packageId', '')
            installPath = package.get('installPath', '')
            # 判断程序包ID是否相等
            if packageId == package_info.get('packageId', ''):
                # 判断程序包路径是否相同,部署路径不同，则修改部署路径
                if installPath != package_info.get('installPath'):
                    package['installPath'] = package_info.get('installPath')
            else:
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
                deploy_policy['packageList'] = [package_info]

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
            logging.error('Full deployment of update policy failed')
        logging.info('Full deployment of update strategy succeeded')

    def run(self):
        try:
            app_info = self.get_app_info()
            if not app_info:
                logging.error('Error getting data information')
                return

            # 判断集群主机是否为空
            cluster_info = app_info.get('cluster_info')
            if len(cluster_info) == 0:
                logging.warning("The number of cluster hosts is zero")
                return

            # 获取集群主机信息，
            deviceList = app_info.get('cluster_info')[0]['deviceList']
            if not deviceList:
                logging.warning('Cluster host is empty, skip and do not process')
                return

            # 部署策略
            logging.info('Getting deployment policy information')
            strategy_info = self.get_strategy_info(app_info)

        except Exception as e:
            logging.error('error %s' % e)
            logging.error('app name is', self.app_instanceId)


# 处理集群信息， 只处理生产环境的集群
class dealCluster():
    def __init__(self, target_id):
        self.instance_id = target_id
        self.cluster_info = self._get_cluster_info()
        if not self.cluster_info:
            logging.error('Failed to get cluster information')
            return

    # 获取集群的信息
    def _get_cluster_info(self):
        # 查询应用
        url = "http://{host}/object/{model}/instance/_search".format(host=easyopsHost, model='CLUSTER')
        search_parse = {
            "query": {
                "instanceId": {
                    "$eq": self.instance_id
                }
            },
            "fields": {"type": True, "appId.instanceId": True, "appId.self_research": True}
        }
        cluster_ret = http_post('POST', url, params=search_parse)
        self.cluster_ret = copy.deepcopy(cluster_ret)
        return self.cluster_ret

    def run(self):
        # [{u'instanceId': u'5b926a348d124', u'_object_id': u'CLUSTER', u'type': u'2', u'appId': [{u'instanceId': u'5b923a86d67d1', u'_object_id': u'APP', u'appId': u'5b923a86d67d1'}]}]
        cluter_type = self.cluster_info[0]['type']  # 集群类型
        appId = self.cluster_info[0]['appId']

        if not appId:
            logging.warning(
                'The cluster information has no application information and will not be processed temporarily')
            return

        # if cluter_type != '2':
        #     logging.warning('Clusters dealing only with production environments')
        #     return

        for app in appId:
            app_instanceId = app.get('instanceId')
            if app.get('self_research') != u"是":
                logging.warning(
                    'The modified application is a non self developed application : %s' % app.get('self_research'))
                break
            for clusterNum in clusterNumList:
                logging.info(
                    u'--------------------the cluster ID to process the deployment policy is: %s, 集群类型 0 开发， 1测试  2生产--------------------' % clusterNum)
                CreateClusterInfo(app_instanceId, clusterNum)


# 调用工具
class Utils:
    @classmethod
    def post_requests(cls, url, headers, data=None):
        if data:
            cmdb_data = requests.post(url=url, headers=headers, data=json.dumps(data))
            status_code = cmdb_data.status_code
            if status_code == 200:
                return cmdb_data.json()
            if status_code == 500:
                logging.warning('请求url - %s - %s - 请求参数 - %s - 警告 - %s' % (url, status_code, data, cmdb_data.json()))
                return False
            else:
                logging.error('请求url - %s - %s - 请求参数 - %s' % (url, status_code, data))
                return False
        else:
            cmdb_data = requests.post(url=url, headers=headers)
            status_code = cmdb_data.status_code
            if status_code == 200:
                return cmdb_data.json()
            else:
                logging.error('请求url - %s - %s - 请求参数 - %s' % (url, status_code, data))
                return False

    @classmethod
    def get_requests(cls, url, headers):
        cmdb_data = requests.get(url=url, headers=headers)
        status_code = cmdb_data.status_code
        if status_code == 200:
            return cmdb_data.json()
        else:
            logging.error('请求url - %s - %s' % (url, status_code))
            return False


class ToolLibrary:
    @classmethod
    def tool_exec(cls, target_ip):
        params = {
            "toolId": TOOLID,
            "inputs": {
                "@agents": [
                    {
                        "ip": target_ip,
                    }
                ],
            },
            "execUser": "root",
            "vId": VID
        }
        url = 'http://{0}/tools/execution'.format(easyopsHost)
        return Utils.post_requests(url, tool_headers, params)

    @classmethod
    def get_tool_exec_result(cls, execid):
        url = 'http://{0}/tools/execution/{1}'.format(easyopsHost, execid)
        return Utils.get_requests(url, tool_headers)


def tool_exec(target_ip):
    """执行工具
    :return: 返回代理IP和执行ID
    """

    try:
        result = ToolLibrary.tool_exec(target_ip)
        code = result.get('code')
        if code == 0:
            data = result.get('data')
            exec_id = data.get('execId')  # 任务ID
            if exec_id:
                logging.info('在服务器执行ip检测工具 - 完成')
                return exec_id
        else:
            logging.warning('在服务器执行ip检测工具 - 失败')
    except Exception:
        logging.warning('实例IP检测工具执行失败,可尝试将工具标记为生产后重试')


def DealData(callback, modelID):
    """
    :param callback: 回调信息
    :param modelID: 模型ID
    :return:
    """

    object_id = callback['data']['ext_info']['object_id']  # 模型ID
    if object_id == "HOST":
        return

    if object_id == 'APP':
        """
        callback['data'] 整体数据
        ext_info 请求创建的数据
        event 类型，创建删除。
        """
        data = callback['data']
        ext_info = data.get('ext_info')
        # 判断是否存在修改权限的数据存在
        diff_data = ext_info.get('diff_data', {}).keys()
        if "productionClusterOperateAuthorizers" in diff_data or "testPipelineOperateAuthorizers" in diff_data or "developPipelineOperateAuthorizers" in diff_data:
            logging.warning(u'应用在修改权限，跳过处理')
            return

        logging.info('消息订阅变更的应用程序的信息ext_info: %s' % ext_info)
        AutoaddApplicationInformation(ext_info).run(data)
        return

    # 处理集群信息
    if callback['data']['target_category'] == 'CLUSTER':
        logging.info('------------------------------------------------------------处理集群信息，创建部署策略')
        target_id = callback['data']['target_id']  # 集群ID
        dealCluster(target_id).run()
        return

    # 应用修改用户后，调用创建权限工具
    try:
        if callback['data']['ext_info']['relation_id'] in ['APP_owner_USER', 'APP_developer_USER', "APP_tester_USER"]:
            exec_id = tool_exec(easyopsHost)
            logging.info('执行权限脚本任务ID：%s' % str(exec_id))
            return
    except Exception as e:
        logging.warning('no relation_id skip: %s' % e)

    # fcode模型
    if object_id == modelID:
        event = callback['data'].get('event')
        if event in ['event.instance.create', ]:  # 只有创建事件的时候才处理
            focdeId = callback['data']['target_id']  # 流水号ID
            name = callback['data']['ext_info']['instance_name']  # 实例名称流水号
            user = callback['data'].get('operator', 'easyops')
            focde_instanceid = callback['data']['ext_info']['instance_id']  # 流水线实例ID

            # 根据focdeId  获取应用名称 /object/@object_id/instance/@instance_id
            url = "http://{host}/object/{id}/instance/{model}".format(host=easyopsHost, id=modelID, model=focdeId)
            app_ret = http_post('GET', url)
            AppName = app_ret.get('application')  # 应用名

            # 根据应用ID，获取对应的Fcode流程管理ID，拼接URL
            search_url = "http://{host}/object/{model}/instance/_search".format(host=easyopsHost, model='APP')
            logging.info('查询{name}应用URL：{url}'.format(name=name, url=search_url))
            search_parse = {
                "query": {
                    "name": {
                        "$eq": AppName
                    }
                }
            }
            logging.info('查询{name}应用参数：{parse}'.format(name=name, parse=search_parse))
            search_ret = http_post('POST', search_url, search_parse)

            flowId = ''
            if search_ret:
                piplineList = search_ret[0].get('__pipeline', [])
                app_instanceId = search_ret[0]['instanceId']  # 应用ID

                for pip in piplineList:
                    pipName = pip.get('name')
                    pipID = pip.get('flowId')
                    if pipName == str('生产环境全量部署(Fcode)'):
                        flowId = pipID
                        break

            if flowId:
                devUrl = 'http://{host}/app/{appid}/pipeline/{flowid}/taskOutputs?page=1'.format(host=domain_name,
                                                                                                 appid=app_instanceId,
                                                                                                 flowid=flowId)
                logging.info(u'应用部署devUrl{url}:'.format(url=devUrl))
                data = {
                    "operator": user,
                    "devUrl": devUrl

                }

                url = "http://{host}/object/{model}/instance/{id}".format(host=easyopsHost, model=modelID,
                                                                          id=focdeId)
                http_post('PUT', url, data)

                # 处理关系
                info_set_url = 'http://{host}/object/APP/relation/{model}/set'.format(host=easyopsHost,
                                                                                      model=modelID)
                info_set_data = {
                    "instance_ids": [app_instanceId],
                    "related_instance_ids": [focde_instanceid]
                }
                http_post('POST', info_set_url, info_set_data)


def application(environ, start_response):
    # 定义文件请求的类型和当前请求成功的code
    try:
        start_response('200 OK', [('Content-Type', 'application/json')])
        # environ是当前请求的所有数据，包括Header和URL，body

        if environ.get("CONTENT_LENGTH") == '':
            return environ
        else:
            request_body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH")))
            callback = json.loads(request_body)
            # 处理数据
            DealData(callback, "FCODE_FLOW")
            return [json.dumps(request_body)]
    except Exception as e:
        logging.warning(e)


if __name__ == "__main__":
    port = 9055
    httpd = make_server(easyopsHost, port, application)
    logging.info("serving http on port {0}...".format(str(port)))
    httpd.serve_forever()
