# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re, copy
import threading
from Queue import Queue
from gevent import monkey

monkey.patch_all()
import gevent
from gevent.pool import Pool

# CMDB配置
easyops_cmdb_host = '192.168.28.28'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索所有实例数据的ID
ConfigSWITCHMODEL = 'HOST'

# 搜索实列列表条件
ConfigParams = {
    "fields": {
        "hostname": True,
        "ip": True,
        "_uuid": True,
    }
}


# Easyops查询实例
class EasyopsPubic(object):
    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        parms = {"path": [
            {"objectId": "BUSINESS", "object_name": "应用系统", "fields": [{"id": "name", "alias_id": "BUSINESS.name"}]},
            {"relation_id": "APP_businesses_BUSINESS", "relation_side_id": "_businesses_APP",
             "relation_side_name": "应用"},
            {"objectId": "APP", "object_name": "应用", "relationDescription": "应用", "fields": []},
            {"relation_id": "APP_clusters_CLUSTER", "relation_side_id": "clusters", "relation_side_name": "集群"},
            {"objectId": "CLUSTER", "object_name": "集群", "relationDescription": "集群", "fields": []},
            {"relation_id": "CLUSTER_deviceList_HOST", "relation_side_id": "deviceList", "relation_side_name": "主机"},
            {"objectId": "HOST", "object_name": "主机", "relationDescription": "主机",
             "fields": [{"id": "hostname", "alias_id": "HOST_主机.hostname"}, {"id": "ip", "alias_id": "HOST_主机.ip"}]}],"page":1,"pageSize":3000, "only_relation_view": True}

        return self.http_post('post', '/path/_search', parms)

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
            page_size = 3000
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
                    if int(data.get('code')) == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


class ThreadInsert(object):
    def __init__(self):
        # 标识num
        self.pool = Pool(40)
        start_time = time.time()
        self.data = self.getData()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        self.inser_data = {}
        st = time.time()
        self.easyopsObj = EasyopsPubic()
        data = self.easyopsObj()['list']
        n = 3  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data[i:i + n] for i in range(0, len(data), n)]
        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for i in content:
            res.append(self.pool.spawn(self.gevent_data, i))

        gevent.joinall(res)

        inser_data = {
            "keys": ['_uuid', 'ip'],
            "datas": []
        }
        for data in res:
            datas = data.get()
            inser_data['datas'].append(datas.values()[0])

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('HOST')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '主机和应用系统关系:', res

    def gevent_data(self, i):
        inser_data = {}
        _uuid = i.get('_uuid')
        ip = i.get('ip')
        businesses_instanceId_list = i.get('_$src_instance_id')
        if not inser_data.has_key(ip):
            inser_data[ip] = {}
        inser_data[ip]['ip'] = ip
        inser_data[ip]['_uuid'] = _uuid
        inser_data[ip]['BUSINESS'] = businesses_instanceId_list

        return inser_data





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
