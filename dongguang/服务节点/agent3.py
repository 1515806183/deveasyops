# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

# CMDB配置
# easyops_cmdb_host = 'admin.easyops.local'
# easyops_org = '1888'
# easy_user = 'peachtao'
easyops_cmdb_host = '192.168.28.28'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索所有主机信息实例数据
ConfigSWITCHMODEL = 'HOST'

# 插入数据模型ID
INSERDATAMODEL = 'MONGODB_SERVICE'

# 搜索实列列表条件
ConfigParams = {"query": {}, "fields": {"instanceId": True, "APP": True, "ip": True}, "only_relation_view": True,
                "only_my_instance": False}


# Easyops查询实例
class EasyopsPubic(object):
    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        return self.instance_search(ConfigSWITCHMODEL, ConfigParams)

    # 搜索实例
    def instance_search(self, object_id, params):
        """
        :param object_id: 配置文件中的搜索模型ID
        :param params: 配置文件中的搜索查询条件
        :return:
        """
        if params.has_key('page_size'):
            page_size = 500
        else:
            page_size = 2000
        params['page_size'] = page_size
        params['page'] = 1
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        if not search_result:
            exit('没有查询到数据')

        total_instance_nums = int(search_result['total'])

        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 1):
                params['page'] = cur_page

                tmp_result = self.http_post(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id), params=params,
                    method='post')
                search_result['list'] += tmp_result['list']

        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params=None):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)
            except Exception as e:
                print e
                return {"list": []}

        elif method in ("info_port",):
            # 这里是交换机端口关联，因为关联成功返回的信息{u'message': u'', u'code': 0, u'data': None, u'error': u''}， 如果像上面那么写 data返回的是None
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if data.get('code') == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False

        elif method in ("info_set",):
            # 会对比关系是否存在, 多余的关系移除掉，不存在的关系添加上
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if data.get('code') == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


class ThreadInsert(object):
    def __init__(self):
        self.host_app_instanceId = {}
        self.easyopsObj = EasyopsPubic()
        self._gethostinstanceId()
        start_time = time.time()
        self.data = self.getData()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def _gethostinstanceId(self):
        """
        获取每台主机下面的app instanceId
        :return:
        """
        host_data = self.easyopsObj()
        for data in host_data:
            ip = data.get('ip')
            app_list = data.get('APP')
            if app_list:
                for app in app_list:
                    if not self.host_app_instanceId.has_key(ip):
                        self.host_app_instanceId[ip] = []
                    self.host_app_instanceId[ip].append(app.get('instanceId'))

    def getnodeapp(self):
        """
        获取 服务的 ip 和 instanceId 为后面建立关系
        :return:
        """
        restful_api = '/object/%s/instance/_search' % INSERDATAMODEL
        params = {"fields": {'name': True}}
        dataList = self.easyopsObj.http_post('post', restful_api, params)

        node_list = []
        # name 为key， instanceId为v
        for data in dataList['list']:
            node_name = data.get('name')
            node_instanceId = data.get('instanceId')
            node_list.append({
                node_name: node_instanceId
            })
        return node_list

    def getData(self):
        st = time.time()
        # 获取oracle数据
        dataList = self.getnodeapp()
        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [dataList[i:i + n] for i in range(0, len(dataList), n)]
        if len(result) > n:
            self.pool = Pool(40)
        else:
            self.pool = Pool(len(result))

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for i in content:
            res.append(self.pool.spawn(self.gevent_data, i))
        gevent.joinall(res)

    def gevent_data(self, i):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        for node_ip, node_instanceId in i.items():
            # 根据IP 从主机+ app instanceId 字典里获取app instanceId
            if self.host_app_instanceId.has_key(node_ip):
                app_instanceId = self.host_app_instanceId.get(node_ip)
                inserdata = {
                    # "object_id": INSERDATAMODEL,
                    # "relation_side_id": 'APP',
                    "instance_ids": [node_instanceId],
                    "related_instance_ids": app_instanceId}

                # url = '/object/{0}/relation/{1}/append'.format(INSERDATAMODEL, 'APP')
                # res = self.easyopsObj.http_post('info_port', url, inserdata)
                # print res
                url = '/object/MONGODB_SERVICE/relation/APP/set'
                res = self.easyopsObj.http_post('info_set', url, inserdata)
                print res


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
    ThreadInsert()
