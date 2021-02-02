# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 根据应用负责人自动添加白名单和角色.py
@time: 2021/1/13 16:49
@desc:自动把负责人信息加入到Fcode开发，测试，生产角色中
    自动给应用加上白名单
'''

import time, requests, json, subprocess, re
import threading, logging, sys
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# CMDB配置
easyops_cmdb_host = str(EASYOPS_CMDB_HOST).split(':')[0]
easyops_org = str(EASYOPS_ORG)
easy_user = 'defaultUser'

# easyops_cmdb_host = '10.163.128.232'
# easyops_org = '3087'

# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

logging.info('Script running environment, host: %s, org: %s' % (easyops_cmdb_host, easyops_org))

# 插入数据模型ID

# 携程池
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

logging.info('Number of script Ctrip: %s' % str(n))


class HTTPRequestException(Exception):

    def __init__(self, message):
        self.message = message
        super(HTTPRequestException, self).__init__(message)


class ResponseTextFormatException(HTTPRequestException):

    def __init__(self):
        message = u'The format of response text is not JSON.'
        super(ResponseTextFormatException, self).__init__(message)


class ResponseCodeException(HTTPRequestException):

    def __init__(self, response_code):
        self.response_code = response_code
        message = u'The response code is {response_code}.'.format(response_code=response_code)
        super(ResponseCodeException, self).__init__(message)


class StatusCodeException(HTTPRequestException):

    def __init__(self, status_code):
        self.status_code = status_code
        message = u'The status code is {status_code}.'.format(status_code=status_code)
        super(StatusCodeException, self).__init__(message)


def http_request(method, host, uri, headers, **kwargs):
    url = u'http://{host}{uri}'.format(host=host, uri=uri)
    response = requests.request(method, url, headers=headers, **kwargs)
    if response.status_code == 200:
        try:
            response_json = json.loads(response.text)
        except ValueError:
            print url
            print ResponseTextFormatException()
            return False
        if response_json['code'] == 0:
            return response_json['data']
        else:
            print url
            print ResponseCodeException(response_json['code'])
            return False
    else:
        print url
        print StatusCodeException(response.status_code)
        return False


class EasyopsPubic(object):

    # 搜索实例
    def instance_search(self, object_id, params):
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        return search_result

    def http_post(self, method, restful_api, params={}):

        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)

        if method in ('post', 'POST'):
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

        elif method in ('get', 'GET'):
            try:
                r = requests.get(url, headers=headers, timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return []

        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    return json.loads(r.content)['code']
            except Exception as e:
                return {"list": []}

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


class ThreadInsert(EasyopsPubic):

    def __init__(self):
        self.userInfo = self.getAppUserInfo()  # 获取app用户信息
        # 将user信息加到对应的角色中

        start_time = time.time()
        self.data = self.getData()
        self.task()
        print("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

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
            "tester": '5fead66e6f2bfaf72a7e0cd5',
            "owner": '5fea90296f2bfaf7297e0cd0',
            "developer": '5ff2759b6f2bfaf7287e0cd2',
        }

        for k, userList in UserDict.items():
            roleID = roldDict[k]
            logging.info('Person in charge information to start processing, roleID: %s, name: %s' % (roleID, k))
            self.__dealUserInfo(roleID, userList)

    def __dealUserInfo(self, roleID, userList):
        logging.info('------------dealuser leader space------------')
        logging.info('user roleID is :%s' % roleID)
        url = ":8085/api/v1/permission_role/config/%s" % roleID
        developerUserInfo = self.http_post('GET', url)  # 平台里面的用户信息

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

    def delUser(self, roleID, removeUserList):
        """
        删除多余的用户
        :param roleID: 角色ID
        :return:
        """
        url = ":8085/api/v1/permission_role/role_delete_user_or_group/%s" % roleID
        params = {
            "operate_user": removeUserList,
            "operate_user_group": []

        }
        ret = self.http_post('PUT', url, params=params)
        return ret

    def addUser(self, roleID, addUserList):
        """
        增加的用户
        :param roleID: 角色ID
        :return:
        """
        url = ":8085/api/v1/permission_role/role_add_user/%s" % roleID
        params = {
            "operate_user": addUserList,
        }
        ret = self.http_post('PUT', url, params=params)
        return ret

    def getAppUserInfo(self):
        """
        获取 用户信息，并将用户加入角色中
        :return:
        """
        logging.info('Start getting user information...')
        testerList = []  # 测试负责人
        ownerList = []  # 运维负责人
        developerList = []  # 开发复制人
        appInstanceIdUser = []  # 返回应用id和用户list

        params = {"fields": {'name': True, 'owner.name': True, 'tester.name': True, "developer.name": True}}

        AppInfoRetList = self.instance_search('APP', params)

        if not AppInfoRetList:
            logging.error('Get data error..')
            exit(1)

        for data in AppInfoRetList:
            try:
                instanceId = data.get('instanceId')
                tester = data.get('tester')
                owner = data.get('owner')
                developer = data.get('developer')

                # 获取每个应用的负责人信息
                real_testerList = [user.get('name') for user in tester if tester]
                real_ownerList = [user.get('name') for user in owner if owner]
                real_developerList = [user.get('name') for user in developer if developer]

                # 保存所有的负责人信息，添加流水线权限用
                testerList += real_testerList
                ownerList += real_ownerList
                developerList += real_developerList

                # 给应用添加白名单用户
                appInfo = {
                    "instanceId": instanceId,
                    # 应用资源实例访问
                    # "readAuthorizers": list(set(real_testerList + real_ownerList + real_developerList + ['easyops'])),
                    # 应用资源实例编辑
                    # "updateAuthorizers": list(set(real_testerList + real_ownerList + real_developerList + ['easyops']))
                    "updateAuthorizers": [],
                    "readAuthorizers": []
                }
                appInstanceIdUser.append(appInfo)

            except Exception as e:
                continue

        logging.info('testerList: %s, ownerList: %s, developerList: %s' % (
            len(list(set(testerList))), len(list(set(ownerList))), len(list(set(developerList)))))
        logging.info('End getting user information...')

        data = {
            "tester": list(set(testerList)),
            "owner": list(set(ownerList)),
            "developer": list(set(developerList)),
        }
        logging.info('Start reporting user to role...')
        self.addUserRole(data)
        logging.info('Pipeline user information cleaned up successfully')
        return appInstanceIdUser

    def getData(self):
        st = time.time()
        result = [self.userInfo[i:i + n] for i in range(0, len(self.userInfo), n)]
        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        res.append(pool.spawn(self.gevent_data, content))
        gevent.joinall(res)

    def gevent_data(self, data):
        """
        :param data: 需要汇报的数据
        :return:
        """
        repo_data = {
            "keys": ['instanceId'],
            "datas": data
        }
        ret = self.http_post('repo', '/object/APP/instance/_import', params=repo_data)

        logging.info('%s --- Report data results, data len: %s, ret: %s' % (
            threading.current_thread().getName(), len(data), ret))

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


def run():
    logging.info('Start executing script...')
    ThreadInsert()


if __name__ == '__main__':
    run()
