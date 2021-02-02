# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 调用工具.py
@time: 2021/1/15 18:04
@desc:
'''
import time
import json
import logging
import requests
import sys
import os
import traceback

USER = "easyops"
ORG = "3087"
CONTENT_TYPE = "application/json"
SERVER_IP = "10.163.128.232"
TOOL_HOST = "tool.easyops-only.com"
TOOLID = 'fa82a4466e65a013662cb05ab1ea132b'  # 工具库ID
VID = '45ac48ca356862173dc32e77c682bd16'  # 工具库版本ID
EXEC_USER = 'root'  # 执行账户
TIME_RESULT = 10  # 获取工具库执行结果的时间间隔

reload(sys)
sys.setdefaultencoding('utf8')

import requests, json, logging, sys

easyops_org = str(EASYOPS_ORG)
cmdb_host = str(EASYOPS_CMDB_HOST).split(':')[0]

easyops_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                   'content-Type': 'application/json'}

# 开发0，测试1，生产2
FcodeType = ""  # fcode程序包版本类型
clusterType = ''  # 0开发， 1 测试， 2生产 集群类型
pageke_env_type = ''  # 1为开发，3为测试，15为生产，程序包版本
if env_type == "生产环境":
    ENV_TYPE = 15
    pageke_env_type = '15'
    clusterType = '2'
    FcodeType = "2"
elif env_type == "测试环境":
    ENV_TYPE = 3
    pageke_env_type = '3'
    clusterType = '1'
    FcodeType = "1"
elif env_type == "预发布环境":
    ENV_TYPE = 7
    pageke_env_type = '7'
else:
    ENV_TYPE = 1
    pageke_env_type = '1'
    clusterType = '0'
    FcodeType = '0'

#################################################################
ORG = EASYOPS_ORG
# 要上传的目标仓库信息
DEPLOY_REPO_IP = EASYOPS_DEPLOY_REPO_HOST
DEPLOY_REPO_HOST = 'deployrepo.easyops-only.com'
DEPLOY_REPO_ENS = 'logic.deploy.repo.archive'

# 需要向生产注册的 deploy 组件信息
# DEPLOY_IP = 'test.proxy.deppon.local'
DEPLOY_IP = EASYOPS_DEPLOY_HOST
DEPLOY_HOST = 'deploy.easyops-only.com'

HEADER = {
    'org': ORG,
    'user': 'defaultUser',
    'Host': '',
}
#################################################################


# Set the logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')


# ftp_url = 'ftp://qaftp.fzzqft.com/fcode_liusha-test_test-dubbo-ifc-index-dubbo-service_master/27/4.0.0.26/'
# version = "4.0.0.26"


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
                "version": version,
                "ftp_file_url": ftp_url,
                "type": FcodeType,  # 开发0，测试1，生产2
            },
            "execUser": EXEC_USER,
            "vId": VID
        }

        headers = {
            "host": TOOL_HOST,
            "user": USER,
            "org": ORG,
            "content-type": CONTENT_TYPE
        }
        url = 'http://{0}/tools/execution'.format(SERVER_IP)
        return Utils.post_requests(url, headers, params)

    @classmethod
    def get_tool_exec_result(cls, execid):
        headers = {
            "host": TOOL_HOST,
            "user": USER,
            "org": ORG,
            "content-type": CONTENT_TYPE
        }
        url = 'http://{0}/tools/execution/{1}'.format(SERVER_IP, execid)
        return Utils.get_requests(url, headers)


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


def get_tool_exec_result(exec_id):
    """得到工具执行结果
    :param proxy_ip: 代理IP
    :param exec_id: 执行ID
    :return:
    """
    result = ToolLibrary.get_tool_exec_result(exec_id)
    code = result.get('code')
    if code == 0:
        data = result.get('data')
        if str(data.get('error')) != 'success':
            logging.error('执行下载程序包失败')
            return False
        tableData = data.get('tableData')['default'][0]
        # {u'default': [{u'PKG_VERSION': u'4.0.5.0', u'_E_TS': u'1610615281649637658', u'UPLOAD_FILE': u'/opt/packages/2021-01-14_17_07_59/deploy-product.tar.gz'}]}
        logging.info('tableData info: %s' % tableData)
        msg = data.get('msg')
        return tableData, msg
    else:
        # 获取执行结果失败
        logging.error('获取ip检测工具执行结果失败 - ', result)
        return False, False


def main(target_ip):
    exec_id = tool_exec(target_ip)  # 执行工具库中的工具
    logging.info('exec_id : %s' % exec_id)
    time.sleep(TIME_RESULT)  # 等待工具执行完成（需预估工具所执行完成的时间）
    ret, msg = get_tool_exec_result(exec_id)  # 获取工具的执行结果
    if ret:
        PKG_VERSION = ret['PKG_VERSION']
        UPLOAD_FILE = ret['UPLOAD_FILE']
        return {"PKG_VERSION": PKG_VERSION, "UPLOAD_FILE": UPLOAD_FILE}, msg

    return False, False


# -----------------------------------------


# Receive a package_id by name
def receive_package_id(name):
    url = 'http://{ip}/package/search'.format(ip=DEPLOY_IP)
    params = {
        'page': 1,
        'pageSize': 200,
        'name': name,
        'type': 1,
    }

    package_id = ''
    headers = HEADER.copy()
    headers['Host'] = DEPLOY_HOST
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        data = resp.json()['data']
        for package in data['list']:
            if package['name'] == name:
                package_id = package['packageId']

    return package_id


# upload to remote deploy repository
def archive(pkg_name, file_path, remark, unzip, strip_first):
    package_id = receive_package_id(pkg_name)
    if not package_id:
        logging.error(u"{file_path}: can't find out the package_id of the package: {pkg_name}".format(
            file_path=file_path, pkg_name=pkg_name))
        PutStr("register_status", u"注册版本失败")
        PutStr("version", version)
        logging.error(u'版本号存在重复，请修改版本号')
        sys.exit(1)

    # create the version
    if os.path.exists(file_path):
        params_dict = {
            'packageId': package_id,
            'message': remark,
            'unzip': unzip,
            'stripFirst': strip_first,
        }
        headers = HEADER.copy()
        headers['Host'] = DEPLOY_REPO_HOST
        url = 'http://{DEPLOY_REPO_IP}/archive'.format(DEPLOY_REPO_IP=DEPLOY_REPO_IP)

        try:
            fps = {'file': open(file_path, 'rb')}
            resp = requests.post(url=url, files=fps, data=params_dict, headers=headers, timeout=300)

            status_code = resp.status_code
            if status_code == 200:
                resp_format = resp.json()
                if resp_format.get('code', None) == 0:
                    data = resp_format['data']

                    logging.info(u'{file_path}: create the version successful'.format(file_path=file_path))
                    return package_id, data
                else:
                    message = resp_format.get('message', '')
                    logging.error(u'{file_path}: create the version failed, reason: {message}'.format(
                        file_path=file_path, message=message))
                    PutStr("register_status", u"注册版本失败")
                    PutStr("version", version)
                    logging.error(u'版本号存在重复，请修改版本号')
                    sys.exit(1)
            else:
                logging.error(u'{file_path}: create the version failed, status: {status}, message: {message}'.format(
                    file_path=file_path, status=status_code, message=resp.text))
                PutStr("register_status", u"注册版本失败")
                PutStr("version", version)
                logging.error(u'版本号存在重复，请修改版本号')
                sys.exit(1)

        except:
            logging.error(u'{file_path}: create the version failed'.format(file_path=file_path))
            logging.error(traceback.format_exc())
            PutStr("register_status", u"注册版本失败")
            PutStr("version", version)
            logging.error(u'版本号存在重复，请修改版本号')
            sys.exit(1)

    else:
        logging.error(u'{file_path}: the file is not exist'.format(file_path=file_path))
        PutStr("register_status", u"注册版本失败")
        PutStr("version", version)
        logging.error(u'版本号存在重复，请修改版本号')
        sys.exit(1)


def register(file_path, package_id, version_info, name, remark, env_type):
    try:
        headers = HEADER.copy()
        headers['content-type'] = 'application/json'
        headers['Host'] = DEPLOY_HOST
        url = 'http://{DEPLOY_IP}/version/sign'.format(DEPLOY_IP=DEPLOY_IP)

        params_dict = {
            'name': name,
            'memo': remark,
            'sign': version_info['sign'],
            # 'conf': version_info.get('conf'),
            'source': {
                'ip': DEPLOY_REPO_IP,
                'port': 80,
                'host': DEPLOY_REPO_HOST,
                'type': 'http',
                'ensName': DEPLOY_REPO_ENS
            },
            'versionId': version_info['id'],
            'packageId': package_id,
            'env_type': env_type,
        }

        resp = requests.post(url=url, json=params_dict, headers=headers, timeout=30)
        if resp.status_code == 200:
            resp_format = resp.json()
            logging.info(u'{file_path}: register successful'.format(file_path=file_path))
        else:
            logging.error(u'{file_path}: register failed, status: {status}, message: {message}'.format(
                file_path=file_path, status=resp.status_code, message=resp.text))
            PutStr("register_status", u"注册版本失败")
            PutStr("version", version)
            logging.error(u'版本号存在重复，请修改版本号')
            sys.exit(1)
    except:
        logging.error(u'{file_path}: register failed'.format(file_path=file_path))
        logger.error(traceback.format_exc())
        PutStr("register_status", u"注册版本失败")
        PutStr("version", version)
        logging.error(u'版本号存在重复，请修改版本号')
        sys.exit(1)


# -------------------------------------------

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
                if (name == version) and (env_type == pageke_env_type):  # 如果版本相同， 环境相同则有这个包
                    versionId = data.get('versionId')  # 程序包版本
                    logging.info('search package name is  %s' % name)
                    logging.info('search package env_type is  %s' % env_type)
                    logging.info('search package versionId is  %s' % versionId)
                    return versionId

        except Exception as e:
            raise Exception('获取应用没有程序包出错')


if __name__ == '__main__':
    # 如果程序包版本不存在，则需要下载程序包
    PutStr("pkg_name", pkg_name)

    if PagekeVersionId == "无":
        logging.info('开始下载包，下载过程可能会比较慢，耐心等待。。。')
        ret, msg = main(SERVER_IP)
        logging.info('下载包并返回内容：%s' % ret)
        for info in str(msg.get(SERVER_IP)).split('\n'):
            logging.info(info)
        # {'PKG_VERSION': u'4.0.0.26', 'UPLOAD_FILE': u'/opt/packages/2021-01-21_14_56_14/deploy-product.tar.gz'}
        if ret:
            # 注册版本

            PKG_NAME = pkg_name
            FILE = ret.get('UPLOAD_FILE')  # 程序包下载路径
            if remark:
                REMARK = remark
            else:
                REMARK = ""
            UNZIP = unzip
            STRIP_FIRST = strip_first
            VERSION = version
            package_id, version_info = archive(pkg_name=PKG_NAME, file_path=FILE, remark=REMARK, unzip=UNZIP,
                                               strip_first=STRIP_FIRST)

            # register the version
            register(file_path=FILE, package_id=package_id, version_info=version_info, name=VERSION, remark=REMARK,
                     env_type=ENV_TYPE)
            PutStr("register_status", u"注册版本成功")
            PutStr("version", version)

            PagekeVersionId = SearchAppPackage().serach_package()  # 获取程序包版本ID

            PutStr("versionId", PagekeVersionId)
            PutStr("UPLOAD_FILE", FILE)

            row = 'register_status={0}&version={1}&versionId={2}&pkg_name={3}&UPLOAD_FILE={4}'.format('注册版本成功', version,
                                                                                                      PagekeVersionId,
                                                                                                      pkg_name, FILE)
            PutRow('default', row)
    else:
        # 不用下载程序包，注册版本

        PutStr("versionId", PagekeVersionId)
        PutStr("UPLOAD_FILE", "无")
        logging.info('Package version: %s exists, no registration required' % version)
        row = 'register_status={0}&version={1}&versionId={2}&pkg_name={3}&UPLOAD_FILE={4}'.format('版本存在，无需注册', version,
                                                                                                  PagekeVersionId,
                                                                                                  pkg_name, "无")
        PutRow('default', row)
