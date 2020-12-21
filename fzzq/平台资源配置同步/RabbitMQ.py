# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from ast import literal_eval

from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

# CMDB配置
easyops_cmdb_host = EASYOPS_CMDB_HOST
easyops_org = EASYOPS_ORG
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

MODEL_ID = 'RABBITMQ_SERVICE'


# Easyops查询实例
class EasyopsPubic(object):

    def __call__(self, *args, **kwargs):
        return self.search_auto_collect()

    def search_auto_collect(self):
        params = {"query": {}, "fields": {"instanceId": True, "name": True, "_SERVICENODE.configInfo": True},
                  "only_relation_view": True, "only_my_instance": False}
        return self.instance_search(MODEL_ID, params)

    # 搜索实例
    def instance_search(self, model_id, params):
        """
        :param object_id: 配置文件中的搜索模型ID
        :param params: 配置文件中的搜索查询条件
        :return:
        """
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=model_id),
                                       params=params)
        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params={}):
        if not params.has_key('page_size'):
            page_size = 300
            params['page_size'] = page_size

        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)

        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    total_instance_nums = int(ret['total'])  # 1252
                    if total_instance_nums > page_size:
                        pages = total_instance_nums / page_size  # total pages = pages + 2
                        for cur_page in range(2, pages + 2):
                            params['page'] = cur_page
                            temp_ret = self.http_post(
                                restful_api=url,
                                params=params,
                                method='post_page')
                            ret['list'] += temp_ret['list']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('post_page',):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    ret = json.loads(r.content)['data']
                    total_instance_nums = int(ret['total'])  # 1252

                    if total_instance_nums > page_size:
                        pages = total_instance_nums / page_size  # total pages = pages + 2
                        for cur_page in range(2, pages + 2):
                            params['page'] = cur_page
                            tmp_result = self.http_post(
                                restful_api=url,
                                params=params,
                                method='page')
                            ret['list'] += tmp_result['list']
                    return ret
            except Exception as e:
                return {"list": []}

        elif method in ('put', 'PUT'):
            try:
                r = requests.put(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['code']
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

        elif method in ('DELETE', 'delete'):
            try:
                r = requests.delete(url, headers=headers, data=json.dumps(params))
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
        self.easyopsObj = EasyopsPubic()
        start_time = time.time()
        self.data = self.getData()
        self.task()
        # self.delete_node()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getData(self):
        st = time.time()
        # 获取oracle数据
        self.dataList = self.easyopsObj()

        n = 20  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [self.dataList[i:i + n] for i in range(0, len(self.dataList), n)]
        if len(result) > n:
            self.pool = Pool(40)
        else:
            self.pool = Pool(len(result))

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for ip in content:
            res.append(self.pool.spawn(self.gevent_data, ip))
        gevent.joinall(res)

        data = {
            "keys": ['name'],
            "datas": []
        }

        for i, g in enumerate(res):
            ret = g.value
            if ret: data['datas'].append(ret)

        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format(MODEL_ID)
            time.sleep(1)
            res = self.easyopsObj.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, data):
        """
        :param i:  每条服务的 ip + instanceId
        :return:
        """
        # 判断IP是否在服务节点里面，如果在的话就pass， 不在新建实例
        listeners = []
        version = ()
        nodes = ()
        rates_mode = ()
        object_totals = ()
        cluster_name = ()
        statistics_db_event_queue = ()
        management_version = ()
        erlang_version = ()
        erlang_full_version = ()
        contexts = []

        name = data.get('name')  # 实例名字
        servernode = data.get('_SERVICENODE')  # 实例服务节点
        configInfo = [True for node in servernode if 'configInfo' in node]  # 判断是否有配置信息，如果有返回True

        if True in configInfo:
            # 循环实例服务节点，取出node
            for node in servernode:
                for key, vaule in node.items():
                    if key != "configInfo": continue
                    for data in vaule:
                        info = data.get('key')
                        if info == 'listeners':
                            ret = data.get('value', [])
                            if isinstance(ret, unicode):
                                if u'node' not in ret:
                                    listeners += literal_eval(ret)
                        elif info == 'version':
                            version += (data.get('value', ''),)
                        elif info == 'node':
                            nodes += (data.get('value', ''),)
                        elif info == 'rates_mode':
                            rates_mode += (data.get('value', ''),)
                        elif info == 'object_totals':
                            object_totals += (data.get('value', ''),)
                        elif info == 'cluster_name':
                            cluster_name += (data.get('value', ''),)
                        elif info == 'statistics_db_event_queue':
                            statistics_db_event_queue += (data.get('value', ''),)
                        elif info == 'management_version':
                            management_version += (data.get('value', ''),)
                        elif info == 'erlang_version':
                            erlang_version += (data.get('value', ''),)
                        elif info == 'erlang_full_version':
                            erlang_full_version += (data.get('value', ''),)
                        elif info == 'contexts':
                            contexts += (json.loads(data.get('value', []))[0],)
            res = {
                "name": name,
                "listeners": self.list_dict_duplicate_removal(listeners),
                "version": tuple(set(version)),
                "nodes": tuple(set(nodes)),
                "rates_mode": tuple(set(rates_mode)),
                "object_totals": tuple(set(object_totals)),
                "cluster_name": tuple(set(cluster_name)),
                "statistics_db_event_queue": tuple(set(statistics_db_event_queue)),
                "management_version": tuple(set(management_version)),
                "erlang_version": tuple(set(erlang_version)),
                "erlang_full_version": tuple(set(erlang_full_version)),
                "contexts": self.list_dict_duplicate_removal(contexts),
            }

            return res

    def list_dict_duplicate_removal(self, data_list):
        run_function = lambda x, y: x if y in x else x + [y]
        return reduce(run_function, [[], ] + data_list)

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
