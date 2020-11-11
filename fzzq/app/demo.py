# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey

monkey.patch_all()
import gevent
from gevent.pool import Pool

# CMDB配置
easyops_cmdb_host = '18.100.254.231'
easyops_org = '3087'
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索实列列表条件
# 搜索所有实例数据的ID
search_model = 'APP'
search_params = {
    "query": {"Auto": True},
    "fields": {
        "name": True,
        "port": True,
        "_SERVICENODE": True,
        "pk": True,
        "featureRule": True
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
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params,
                                       object_id=object_id)
        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params={}, object_id=None):
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
                                restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                params=params,
                                method='post_page')
                            ret['list'] += temp_ret['list']
                    return ret
            except Exception as e:
                print e
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

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)
            except Exception as e:
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

        data = {
            "keys": ['name'],
            "datas": []
        }
        for i, g in enumerate(res):
            if g.value: data['datas'].append(g.value)

        print data

        # 插入数据到模型
        # if len(data['datas']):
        #     info_url = "/object/{0}/instance/_import".format('APP')
        #     res = self.easyopsObj.http_post('many_post', info_url, data)
        #     print res

    def gevent_data(self, data):
        pk = int(data.get('pk'))  # 标识
        name = data.get('name')  # 应用名称
        ServiceNode = data.get('_SERVICENODE')  # 服务节点
        port = data.get('port')  # 端口
        featureRule = data.get('featureRule')  # 特征
        file_name = str(name).split('_')[1]  # 分解出工作目录
        # instanceId = data.get('instanceId')

        # ServiceNodeUrl = "/v2/object/APP/instance/%s" % instanceId  # 添加服务节点url
        if pk < 4:
            ServiceNodeData = {}

            # 判断是不是新应用，新应用：服务节点为空，特性为空
            if (not len(ServiceNode)) and (not featureRule):
                # 1. 新应用，默认添加工作目录为特性。
                ServiceNodeData = {"featurePriority": "500", "featureEnabled": "true", "featureRule": [
                    {"key": "provider.cwd", "method": "like", "value": "%s" % file_name, "label": "工作目录"}]}

            # 如果不是新应用, 服务节点为None，特性为True，修改特性里面的key port(端口)， type（节点类型）,假设只配置了一个特性
            elif (not len(ServiceNode)) and featureRule:
                # 循环取特性项
                try:
                    for rule in featureRule:
                        if rule.get('key') == 'provider.cwd':
                            # 修改特性为port
                            if port:
                                # 端口特性
                                ServiceNodeData = {"featurePriority": "500", "featureEnabled": "true", "featureRule": [
                                    {"key": "port", "method": "eq", "value": "%s" % port, "label": "监听端口"}]}
                            else:
                                # 关闭特性
                                ServiceNodeData = {"featurePriority": "500", "featureEnabled": "false"}
                        elif rule.get('key') == 'port':
                            # 修改特性为type
                            ServiceNodeData = {"featurePriority": "500", "featureEnabled": "true", "featureRule": [
                                {"key": "provider.cwd", "method": "like", "value": "%s" % file_name, "label": "工作目录"}]}
                except Exception as e:
                    print e

            # 标识相加，如果当标识等于3，则判断，节点特性取不到数据
            pk += 1

            return dict({
                "name": name,
                "pk": pk,
                "remarks": ''
            }, **ServiceNodeData)

        elif (len(ServiceNode) == 0) and (pk > 3):
            return {
                "name": name,
                "pk": pk,
                "remarks": "节点发现服务-未发现节点，请修改特性。",
                "featureEnabled": "false"
            }

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
