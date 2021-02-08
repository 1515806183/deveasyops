# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: update_app.py
@time: 2021/2/1 17:15
@desc: 同步自研应用的必填属性
'''
import time, requests, json, subprocess, re
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

cmdb_host = "10.163.128.232"
easyops_org = "3087"

cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}

deploy_headers = {
    'host': "deploy.easyops-only.com",
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


class AutoUpdateAppAttr():
    def __init__(self):
        start_time = time.time()
        self.data = self.getData()  # 获取应用信息
        self.task()
        logging.info("========= 增加更新实例数据完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getAppInfo(self):
        """
        获取 应用信息
        :return:
        """
        url = "http://{HOST}/object/{ID}/instance/_search".format(HOST=cmdb_host, ID="APP")
        params = {
            "query": {"self_research": {"$eq": u"是"}},
            "fields": {'name': True, "_packageList": True}}

        dataList = http_post('POSTS', url, params)

        if len(dataList) == 0:
            logging.warning('There is no instance data in the CMDB platform {MODELE}'.format(MODELE="APP"))

        return dataList

    def getData(self):
        st = time.time()
        # 获取现网服务数据
        self.dataList = self.getAppInfo()

        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]

        logging.info("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def gevent_data(self, data):
        """
        :param i:  每条应用信息
        :return:
        """
        AppName = data.get('name')
        _packageList = data.get('_packageList')
        deploy_user = ''
        inser_data = {}
        for package in _packageList:
            packageId = package.get("packageId")
            # 如果程序包名称和应用名称一致，则为当前应用的程序包
            # 通过程序包ID获取程序包信息
            url = "http://{HOST}/package/{ID}".format(HOST=cmdb_host, ID=packageId)
            pack_ret = http_post('GET', url, headers=deploy_headers)
            pack_name = pack_ret.get('name')
            if AppName == pack_name:
                logging.info('AppName: %s ,找到了应用关联的程序包 packageId: %s' % (AppName, packageId))
                pack_conf = pack_ret.get('conf')
                platform_type = pack_ret.get('platform').capitalize()
                installPath = pack_ret.get('installPath')
                pack_conf = pack_conf.replace("\n", " ")

                try:
                    deploy_user = str(re.search('user:\s+(\w+)', pack_conf).group(1)).strip()
                except Exception as e:
                    logging.warning('没设置部署用户')

                if deploy_user:
                    inser_data['deploy_user'] = deploy_user

                inser_data['install_path'] = installPath.strip()
                inser_data['platform_type'] = platform_type.strip()
                inser_data['self_research'] = u"是"
                inser_data['Auto'] = True
                inser_data['name'] = AppName
                break
        if inser_data: return inser_data

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            url = "http://{HOST}/object/{ID}/instance/_import".format(HOST=cmdb_host, ID="APP")
            time.sleep(1)
            res = http_post('repo', url, data)
            logging.info('Return of inserted data: %s' % res)
        else:
            logging.info('There is no data to insert')

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
    AutoUpdateAppAttr()
