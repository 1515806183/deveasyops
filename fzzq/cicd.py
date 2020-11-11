#!/usr/local/easyops/python/bin/python
# -*- coding: utf-8 -*-

import logging
import requests
import sys
import os
import traceback
import json
import datetime

#################################################################
# Custom configuration area
ORG = 'foundersc'
DEPLOY_REPO_IP = EASYOPS_DEPLOY_HOST
DEPLOY_REPO_HOST = 'deployrepo.easyops-only.com'
DEPLOY_REPO_ENS = 'logic.deploy.repo.archive'

DEPLOY_IP = EASYOPS_DEPLOY_HOST
DEPLOY_HOST = 'deploy.easyops-only.com'

# DEPLOY_REPO_IP = EASYOPS_DEPLOY_HOST #'42.159.91.26'
# DEPLOY_REPO_HOST = 'deployrepo.easyops-only.com'

# DEPLOY_IP = EASYOPS_DEPLOY_HOST
# DEPLOY_IP = EASYOPS_DEPLOY_HOST #'42.159.91.26'
# DEPLOY_HOST = 'deploy.easyops-only.com'

HEADER = {
    'org': EASYOPS_ORG,
    'user': EASYOPS_USER,
    'Host': '',
}
#################################################################


# Set the logger
FORMAT = '[%(asctime)s %(filename)s(line:%(lineno)d) %(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger('log')
logger.setLevel(logging.DEBUG)


#
class PackageMgr():
    def __init__(self, pkgname):
        self.pkgname = pkgname
        self.packageId = ''
        self.lastversion = ''
        self.headers = {
            'org': EASYOPS_ORG,
            'user': EASYOPS_USER,
            'Host': DEPLOY_HOST
        }

    def output(self):
        PutStr("PACKAGE_NAME", self.pkgname)
        PutStr("VERSION_NAME", pkg_version)
        PutStr("COMMENT", pkg_comment)
        PutStr("VERSION_ID", self.lastversion)

        info = "PACKAGE_NAME={0}&PACKAGE_ID={1}&VERSION_NAME={2}&VERSION_ID={3}&COMMENT={4}".format(self.pkgname,
                                                                                                    self.packageId,
                                                                                                    pkg_version,
                                                                                                    self.lastversion,
                                                                                                    pkg_comment)
        PutRow("table", info)

        return 0

    def create_package(self):
        res, packageId, lastversion = self.search_package()
        if res < 0:
            logger.error("search package failed!")
            sys.exit(3)

        if res > 0:
            self.packageId = packageId
            self.lastversion = lastversion
            return 0

        # new app, create package
        url = u"http://{host}/package".format(host=DEPLOY_IP)
        try:
            params_dict = {
                'name': package_name,
                'type': 1,
                'cId': 1,
                'memo': 'auto pipeline  ' + package_name,
                'installPath': install_path + '/' + package_name
            }
            http_ret = requests.post(url=url, headers=self.headers,
                                     data=params_dict, timeout=60)
            if http_ret.status_code == 200:
                ret_obj = json.loads(http_ret.content)
                if ret_obj['code'] == 0:
                    self.packageId = ret_obj['data']['packageId']
                    self.lastversion = ''
                else:
                    self.packageId = ''
            else:
                logger.error(http_ret.text)
                sys.exit(3)
        except Exception:
            logger.error(traceback.format_exc())
            sys.exit(4)

    # check
    def search_package(self):
        url = u"http://{host}/package/search".format(host=DEPLOY_IP)
        logger.info(url)
        logger.info(self.headers)
        try:
            params_dict = {
                'name': self.pkgname,
                'type': 1,
                'page': 1,
                'pageSize': 1
            }
            http_ret = requests.get(url=url, headers=self.headers,
                                    params=params_dict, timeout=60)
            if http_ret.status_code == 200:
                ret_obj = json.loads(http_ret.text)
                logger.info(ret_obj)
                total = ret_obj['data']['total']
                if total == 0:
                    return total, '', ''
                else:
                    packageId = ret_obj['data']['list'][0]['packageId']
                    versionname = ret_obj['data']['list'][0]['lastVersionInfo']['name']

                    logger.info("Find {total} packages, the first pkg guid is: {pkgid}, versionname: {version}".format(
                        total=total, pkgid=packageId, version=versionname))
                    return total, packageId, versionname
            else:
                logger.error(http_ret.text)
                return -1, '', ''
        except Exception:
            logger.error(traceback.format_exc())
            return -1, '', ''

    # Receive a package_id by name
    def receive_package_id(self, name):
        url = 'http://{ip}/package/search'.format(ip=DEPLOY_IP)
        params = {
            'page': 1,
            'pageSize': 200,
            'name': name,
            'type': PACKAGE_TYPE,
        }

        package_id = ''
        headers = self.headers.copy()
        headers['Host'] = DEPLOY_HOST
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            data = resp.json()['data']
            for package in data['list']:
                if package['name'] == name:
                    package_id = package['packageId']

        return package_id

    def delete_workspace(self):
        # package_id = self.receive_package_id(pkg_name)
        package_id = self.packageId
        logger.info(package_id)
        headers = self.headers.copy()
        headers['Host'] = DEPLOY_REPO_HOST
        url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=DEPLOY_REPO_IP,
                                                                      PACKAGE_ID=package_id)
        logger.info(url)
        logger.info(headers)
        resp = requests.delete(url=url, headers=headers, timeout=300)

        status_code = resp.status_code
        if status_code == 200:
            resp_format = resp.json()
            if resp_format.get('code', None) == 0:
                data = resp_format['data']

                logger.info('clear the workspace successful')
                return package_id, data
            else:
                message = resp_format.get('message', '')
                logger.error('clear the workspace failed, reason: {message}'.format(message=message))
                sys.exit(1)
        else:
            logger.error('clear the workspace failed')

    # upload to remote deploy repository workspace
    def workspace(self, file_path):
        # package_id = self.receive_package_id(pkg_name)
        package_id = self.packageId
        if not package_id:
            logger.error("{file_path}: can't find out the package_id of the package: {pkg_name}".format(
                file_path=file_path, pkg_name=package_name))
            sys.exit(1)

        # create the version
        if os.path.exists(file_path):
            headers = self.headers.copy()
            headers['Host'] = DEPLOY_REPO_HOST
            url = 'http://{DEPLOY_REPO_IP}/workspace/{PACKAGE_ID}/upload'.format(DEPLOY_REPO_IP=DEPLOY_REPO_IP,
                                                                                 PACKAGE_ID=package_id)
            logger.info(url)
            logger.info(headers)
            try:
                fps = {'file': open(file_path, 'rb')}
                path_file = '/'
                params_dict = {
                    'path': path_file,
                    'decompress': 'true',
                    'strip': 'true',
                }
                resp = requests.post(url=url, files=fps, data=params_dict, headers=headers, timeout=300)

                status_code = resp.status_code
                if status_code == 200:
                    resp_format = resp.json()
                    if resp_format.get('code', None) == 0:
                        data = resp_format['data']

                        logger.info('{file_path}: upload the version successful'.format(file_path=file_path))
                        return package_id, data
                    else:
                        message = resp_format.get('message', '')
                        logger.error('{file_path}: upload the version failed, reason: {message}'.format(
                            file_path=file_path, message=message))
                        sys.exit(1)
                else:
                    logger.error('{file_path}: upload the version failed, status: {status}, message: {message}'.format(
                        file_path=file_path, status=status_code, message=resp.text.encode('utf-8')))
                    sys.exit(1)

            except:
                logger.error('{file_path}: upload the version failed'.format(file_path=file_path))
                logger.error(traceback.format_exc())
                sys.exit(1)

        else:
            logger.error('{file_path}: the file is not exist'.format(file_path=file_path))
            sys.exit(1)

    def register(self):
        try:
            headers = self.headers.copy()
            headers['content-type'] = 'application/json'
            headers['Host'] = DEPLOY_REPO_HOST
            url = 'http://{DEPLOY_REPO_IP}/v2/workspace/{PACKAGE_ID}'.format(DEPLOY_REPO_IP=DEPLOY_REPO_IP,
                                                                             PACKAGE_ID=self.packageId)
            logger.info(url)
            logger.info(headers)
            pkg_version = 1.0
            if self.lastversion != '':
                pkg_version = float(self.lastversion) + 0.1

            params_dict = {
                'name': str(pkg_version),
                'message': pkg_comment,
                'env_type': 3
            }

            resp = requests.post(url=url, json=params_dict, headers=headers, timeout=30)
            if resp.status_code == 200:
                resp_format = resp.json()
                self.lastversion = resp_format['data']
                logger.info('{file_path}: register successful'.format(file_path=UPLOAD_FILE))
            else:
                # logger.error('{file_path}: register failed, status: {status}, message: {message}'.format(
                #    file_path=file_path, status=resp.status_code, message=resp.text.encode('utf-8')))
                logger.error('error:文件没有变更或版本名称重复')
                sys.exit(1)
        except:
            logger.error('{file_path}: register failed'.format(file_path=UPLOAD_FILE))
            logger.error(traceback.format_exc())
            sys.exit(1)


if __name__ == '__main__':
    # default upload the app package
    pkgmgr = PackageMgr(package_name)
    pkgmgr.create_package()

    logger.info('清理工作区...')
    pkgmgr.delete_workspace()
    logger.info('上传文件到工作区...')
    pkgmgr.workspace(file_path=UPLOAD_FILE)
    logger.info('上传配置文件到工作区...')
    pkgmgr.workspace(file_path=CONFIG_FILE)
    logger.info('提交工作区文件并注册版本...')
    pkgmgr.register()

    pkgmgr.output()
    sys.exit(0)