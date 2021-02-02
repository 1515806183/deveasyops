# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: service_node.py
@time: 2021/1/26 12:17
@desc:应用系统关联主机
'''
import time, requests, json, subprocess, re, random
import threading, logging, sys
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

reload(sys)
sys.setdefaultencoding('utf8')
monkey.patch_all()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# 携程池
n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)

easyops_cmdb_host = str(EASYOPS_CMDB_HOST).split(':')[0]
easyops_org = str(EASYOPS_ORG)

cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}


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

    elif method in ('DELETE', 'delete'):
        try:
            r = requests.delete(url, headers=headers, data=json.dumps(params), timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                return data
            else:
                return r.content
        except Exception as e:
            return e


# 应用关联主机和应用系统，加清理机制
class HostAssociation():
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 现网数据
        self.task()
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getAppInfo(self):
        """
        获取 应用信息，主要获取应用里面的主机信息和应用现存的HOST信息
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="BUSINESS")
        # "query": {"name": {"$eq":
        #                        "maxguage"
        #                    }},
        params = {"fields": {'name': True, "_businesses_APP.clusters.deviceList.ip": True}}
        dataList = http_post('POSTS', url, params)
        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE="BUSINESS"))
        return dataList

    def getData(self):
        st = time.time()
        # 获取现网服务数据
        self.dataList = self.getAppInfo()  # 获取服务对应的服务节点列表（平台内的数据）

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def gevent_data(self, data):
        """
        :param i:  每台哦应用实例信息
        :return:
        """
        businesses_id = data.get('instanceId')
        businesses_name = data.get('name')
        _businesses_APP = data.get('_businesses_APP', [])
        if not _businesses_APP: return

        LatestHostList = []
        for app in _businesses_APP:
            try:
                clustersList = app.get('clusters', [])
            except Exception as e:
                logging.warning('get app clustersList error, %s' % str(e))
                clustersList = []  # list

            # 应用系统获取应用集群里面的主机
            for clusters in clustersList:
                try:
                    deviceList = clusters.get('deviceList', [])
                    if not deviceList: continue
                    for device in deviceList:
                        hostInstanceId = device.get('instanceId')
                        LatestHostList.append(hostInstanceId)
                except Exception as e:
                    logging.info('应用系统获取集群主机信息报错:%s' % str(e))
                    continue

        logging.info(str('应用系统:%s, 最新主机数量为:%s' % (businesses_name, len(list(set(LatestHostList))))))
        # 会对比关系是否存在, 多余的关系移除掉，不存在的关系添加上
        url = "http://{HOST}/object/{ID}/relation/{relation_side_id}/set".format(HOST=cmdb_host,
                                                                                 ID="BUSINESS", relation_side_id="HOST")

        data = {
            "instance_ids": [businesses_id],
            "related_instance_ids": list(set(LatestHostList))
        }
        res = http_post('POST', url, params=data)
        logging.info('应用关联主机关系返回结果:%s' % res)

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

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
    HostAssociation()
