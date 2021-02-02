# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: update_process.py
@time: 2021/1/13 11:51
@desc:
'''
import time, requests, json, sys, logging
import threading
from Queue import Queue
from ast import literal_eval

from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()
reload(sys)
sys.setdefaultencoding('utf8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

tool_headers = {
    "host": "tool.easyops-only.com",
    "org": "3087",
    "user": "easyops",
    "content-Type": "application/json"
}

deploy_headers = {
    "content-Type": "application/json",
    "host": "deploy.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

cmdb_headers = {
    "content-Type": "application/json",
    "host": "cmdb_resource.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

cmdb_host = "10.163.128.232"

# 携程池
n = 2  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)


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
                code = str(json.loads(r.content)['code'])
            except Exception as e:
                ret = json.loads(r.content)
                code = '1'
            return code, ret

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


class AssemblyLineDemo(object):
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getData(self):
        """
        获取平台所有自研应用，初始化了流水线模板的应用
        :return:
        """
        logging.info('Start getting app information....')
        url = 'http://{HOST}/object/APP/instance/_search'.format(HOST=cmdb_host)
        params = {
            "query": {
                "self_research": {
                    "$eq": "否"
                },
                "init_package": {
                    "$eq": False
                }

            },
            "fields": {"name": True, "_packageList": True},
        }
        logging.info('search app params : %s' % params)
        app_data_list = http_post('POSTS', url, params=params)
        result = [app_data_list[i:i + n] for i in range(0, len(app_data_list), n)]
        logging.info('应用信息共获取{}组数据,每组{}个元素'.format(len(result), n))
        return result

    def dealdata(self, content):
        res = []
        for data in content:
            res.append(pool.spawn(self.gevent_data, data))
        gevent.joinall(res)

    def gevent_data(self, data):
        name = str(data.get('name'))
        instanceId = data.get('instanceId')
        logging.info('app name is : %s' % name)

        url = u"http://{host}/package".format(host=cmdb_host)
        params = {
            "name": name,
            "cId": 1,
            "type": 1,
            "installPath": '/root',
            "platform": 'linux',
            "memo": "auto create"
        }
        try:
            ret = http_post('POST', url, params, headers=deploy_headers)
            packageId = ret.get('data')['packageId']
            installPath = '/root'
            logging.info('packageId is :%s' % packageId)
            logging.info('create package success')

        except Exception as e:
            logging.warning('获取程序包信息')
            # 表示包存在
            # 查询包
            url = 'http://{HOST}/package/search?name={appname}&page=1&pageSize=10&exact=true'.format(HOST=cmdb_host,
                                                                                                     appname=name)
            ret = http_post('GET', url, headers=deploy_headers)
            packageId = ret['list'][0].get('packageId')
            installPath = ret['list'][0].get('installPath')

        # 8113
        url = u"http://{host}:8113/app/{ID}/package".format(host=cmdb_host, ID=instanceId)

        # [{"installPath":"/root","packageId":"836e109959e6e0f59b6ee83a63be6f7a"}]
        params = [{"packageId": packageId, "installPath": installPath}]

        ret = http_post('POST', url, params=params, headers=deploy_headers)
        logging.info('应用名称: %s,Application related package information :%s' % (name, ret))
        code = str(ret.get('code'))
        if code == '0':
            # 标识程序包已经初始化程序包，并关联应用了
            url = 'http://{HOST}/object/APP/instance/{ID}'.format(HOST=cmdb_host, ID=instanceId)
            params = {
                "init_package": True
            }
            code, ret = http_post('PUT', url, params)
            logging.info('app name :%s, 更新了是否初始化程序包，状态：%s' % (name, code))

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


if __name__ == '__main__':
    AssemblyLineDemo()
