# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
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
# 搜索实列列表条件
# 搜索所有实例数据的ID
search_model = 'APP'
search_params = {
    "fields": {
        "name": True,
        "_SERVICENODE": True
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
        return self.instance_search(search_model, search_params)

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
            page_size = 1000
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

        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['code']
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
                    if int(data.get('code')) == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


class ThreadInsert(object):
    def __init__(self):
        self.pool = Pool(40)
        start_time = time.time()
        self.data = self.getData()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        st = time.time()
        self.easyopsObj = EasyopsPubic()
        data = self.easyopsObj()
        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data[i:i + n] for i in range(0, len(data), n)]
        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for i in content:
            res.append(self.pool.spawn(self.gevent_data, i))
        gevent.joinall(res)

    def gevent_data(self, data):
        servicenode = data.get('_SERVICENODE')
        # 为空才进行下一步判断
        if not servicenode:
            app_name = data.get('name')
            app_instanceId = data.get('instanceId')
            # 中间件件
            name_list = ['tomcat', 'nginx', u'中间件', 'zookeeper', 'hadoop', 'inceptor', 'fdfs_trackerd', 'fdfs_storaged',
                         'kafka', 'activemq', 'rabbitmq', 'hsserver']

            # 插入节点自动发现url
            inser_node_url = '/object/APP/instance/' + app_instanceId

            for name in name_list:
                if name in app_name:
                    # 增加中间件节点发现值
                    type_name = 'tomcat|nginx|zookeeper|hadoop|inceptor|fdfs_trackerd|fdfs_storaged|kafka|activemq|rabbitmq|hsserver'

                    # 插入节点自动发现参数
                    parma = {"featurePriority": "500", "featureEnabled": "true",
                             "featureRule": [{"key": "type", "method": "eq", "value": type_name, }]}
                    res = self.easyopsObj.http_post('put', inser_node_url, parma)
                    if int(res) == 0:
                        print '应用添加中间件自动发现节点成功：', app_name
                    break
            # 数据库
            name_list = [u'数据库', 'sqlserver', 'mysql', 'redis', 'mongodb', 'oracle', 'hadoop', 'redis-sentinel']
            for name in name_list:
                if name in app_name:
                    # 增加中间件节点发现
                    sql_name = 'sqlserver|mysql|redis|mongodb|oracle|hadoop|redis-sentinel'
                    # 插入节点自动发现参数
                    parma = {"featurePriority": "500", "featureEnabled": "true",
                             "featureRule": [{"key": "type", "method": "eq", "value": sql_name, }]}
                    res = self.easyopsObj.http_post('put', inser_node_url, parma)
                    if int(res) == 0:
                        print '应用添加数据库自动发现节点成功：', app_name
                    break

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
