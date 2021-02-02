# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: elasticsearch配置同步.py
@time: 2020/12/2 10:14
@desc:应用部署-统计所有应用部署情况
'''

import time, requests, json
import threading
from Queue import Queue
from ast import literal_eval

from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

# CMDB配置
easyops_cmdb_host = '18.100.254.231'
easyops_org = '3087'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': 'defaultUser', 'content-Type': 'application/json'}

# 携程池
n = 5  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
pool = Pool(20)


# Easyops查询实例
class EasyopsPubic(object):

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
                                restful_api=restful_api,
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
                print e
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


class ThreadInsert(EasyopsPubic):
    def __init__(self):
        app_list = self.instance_search('APP', {"query": {},
                                                "fields": {"instanceId": True, "name": True,
                                                           "businesses.instanceId": True}, "page": 1})

        start_time = time.time()
        self.data = self.getData(app_list)
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    def getData(self, app_list):
        """
        :param app_list: 应用列表
        :return:
        """
        st = time.time()
        result = [app_list[i:i + n] for i in range(0, len(app_list), n)]

        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

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
            info_url = "/object/{0}/instance/_import".format('app_deploy_count')
            time.sleep(1)
            res = self.http_post('many_post', info_url, data)
            print res

    def gevent_data(self, data):
        """
        :param data: 5条应用信息为一组，每次取一条
        :return:
        """
        businessesId = ''
        businesses_list = data.get('businesses')
        if len(businesses_list) != 0:
            businessesId = businesses_list[0].get('instanceId')

        AppInstanceId = data.get('instanceId')
        AppName = data.get('name')

        # 根据AppInstanceId 到DEPLOY_DASHBOARD模型中获取数据
        params = {
            "query": {"appInstanceId": {
                "$eq": AppInstanceId
            }},
            "fields":
                {},
            "page": 1}

        search_info = self.instance_search('DEPLOY_DASHBOARD', params)

        # 生产数据 2
        runningCount_total = 0
        successCount_total = 0
        failedCount_total = 0
        deployCount_total = 0
        deployManualCount_total = 0
        deployStrategyCount_total = 0
        timeConsume_total = 0
        num_total = 0

        # 开发数据 0
        runningCount_dev = 0
        successCount_dev = 0
        failedCount_dev = 0
        deployCount_dev = 0
        deployManualCount_dev = 0
        deployStrategyCount_dev = 0
        timeConsume_dev = 0
        num_dev = 0

        # 测试数据 1
        runningCount_qa = 0
        successCount_qa = 0
        failedCount_qa = 0
        deployCount_qa = 0
        deployManualCount_qa = 0
        deployStrategyCount_qa = 0
        timeConsume_qa = 0
        num_qa = 0

        # 预发布 3
        runningCount_uat = 0
        successCount_uat = 0
        failedCount_uat = 0
        deployCount_uat = 0
        deployManualCount_uat = 0
        deployStrategyCount_uat = 0
        timeConsume_uat = 0
        num_uat = 0

        if search_info:
            for info in search_info:
                clusterInfoList = info.get('clusterInfoList')
                for cluster in clusterInfoList:
                    clusterType = cluster.get('clusterType')  # 部署集群版本，生产是2

                    runningCount = cluster.get('runningCount')  # 进行中任务
                    successCount = cluster.get('successCount')  # 成功任务
                    failedCount = cluster.get('failedCount')  # 失败任务
                    deployCount = cluster.get('deployCount')  # 部署次数
                    deployManualCount = cluster.get('deployManualCount')  # 手动部署次数
                    deployStrategyCount = cluster.get('deployStrategyCount')  # 部署策略部署次数
                    timeConsume = cluster.get('timeConsume')  # 平均耗时(秒)

                    # 开发
                    if clusterType == 0:
                        runningCount_dev += runningCount
                        successCount_dev += successCount
                        failedCount_dev += failedCount
                        deployCount_dev += deployCount
                        deployManualCount_dev += deployManualCount
                        deployStrategyCount_dev += deployStrategyCount
                        timeConsume_dev += timeConsume
                        num_dev += 1

                    # 测试
                    elif clusterType == 1:
                        runningCount_qa += runningCount
                        successCount_qa += successCount
                        failedCount_qa += failedCount
                        deployCount_qa += deployCount
                        deployManualCount_qa += deployManualCount
                        deployStrategyCount_qa += deployStrategyCount
                        timeConsume_qa += timeConsume
                        num_qa += 1

                    # 生产
                    elif clusterType == 2:
                        runningCount_total += runningCount
                        successCount_total += successCount
                        failedCount_total += failedCount
                        deployCount_total += deployCount
                        deployManualCount_total += deployManualCount
                        deployStrategyCount_total += deployStrategyCount
                        timeConsume_total += timeConsume
                        num_total += 1

                    # 预发布
                    elif clusterType == 3:
                        runningCount_uat += runningCount
                        successCount_uat += successCount
                        failedCount_uat += failedCount
                        deployCount_uat += deployCount
                        deployManualCount_uat += deployManualCount
                        deployStrategyCount_uat += deployStrategyCount
                        timeConsume_uat += timeConsume
                        num_uat += 1

            ret = {
                "name": AppName,
                "BUSINESS": businessesId,
                "appInstanceId": AppInstanceId,
                "APP": AppInstanceId,
                "clusterInfoList": []
            }
            # 生产
            pro = {
                "clusterType": '生产',
                "runningCount": runningCount_total,
                "successCount": successCount_total,
                "failedCount": failedCount_total,
                "deployCount": deployCount_total,
                "deployManualCount": deployManualCount_total,
                "deployStrategyCount": deployStrategyCount_total,
                "timeConsume": 0,
            }
            if num_total != 0:
                pro['timeConsume'] = round(timeConsume_total / num_total, 2)

            ret['clusterInfoList'].append(pro)

            # 开发
            dev = {
                "clusterType": '开发',
                "runningCount": runningCount_dev,
                "successCount": successCount_dev,
                "failedCount": failedCount_dev,
                "deployCount": deployCount_dev,
                "deployManualCount": deployManualCount_dev,
                "deployStrategyCount": deployStrategyCount_dev,
                "timeConsume": 0,
            }
            if num_dev != 0:
                dev['timeConsume'] = round(timeConsume_dev / num_dev, 2)

            ret['clusterInfoList'].append(dev)

            # 测试
            qa = {
                "clusterType": '测试',
                "runningCount": runningCount_qa,
                "successCount": successCount_qa,
                "failedCount": failedCount_qa,
                "deployCount": deployCount_qa,
                "deployManualCount": deployManualCount_qa,
                "deployStrategyCount": deployStrategyCount_qa,
                "timeConsume": 0,
            }
            if num_qa != 0:
                qa['timeConsume'] = round(timeConsume_qa / num_qa, 2)

            ret['clusterInfoList'].append(qa)

            # 预发布
            uat = {
                "clusterType": '预发布',
                "runningCount": runningCount_uat,
                "successCount": successCount_uat,
                "failedCount": failedCount_uat,
                "deployCount": deployCount_uat,
                "deployManualCount": deployManualCount_uat,
                "deployStrategyCount": deployStrategyCount_uat,
                "timeConsume": 0,
            }
            if num_uat != 0:
                uat['timeConsume'] = round(timeConsume_uat / num_uat, 2)

            ret['clusterInfoList'].append(uat)

            return ret
        else:

            ret = {
                "name": AppName,
                "BUSINESS": businessesId,
                "appInstanceId": AppInstanceId,
                "APP": AppInstanceId,
                'clusterInfoList': []
            }
            # 生产
            pro = {
                "clusterType": '生产',
                "runningCount": runningCount_total,
                "successCount": successCount_total,
                "failedCount": failedCount_total,
                "deployCount": deployCount_total,
                "deployManualCount": deployManualCount_total,
                "deployStrategyCount": deployStrategyCount_total,
                "timeConsume": 0,

            }
            if num_total != 0:
                pro['timeConsume'] = round(timeConsume_total / num_total, 2)

            ret['clusterInfoList'].append(pro)

            # 开发
            dev = {
                "clusterType": '开发',
                "runningCount": runningCount_dev,
                "successCount": successCount_dev,
                "failedCount": failedCount_dev,
                "deployCount": deployCount_dev,
                "deployManualCount": deployManualCount_dev,
                "deployStrategyCount": deployStrategyCount_dev,
                "timeConsume": 0,

            }
            if num_dev != 0:
                dev['timeConsume'] = round(timeConsume_dev / num_dev, 2)

            ret['clusterInfoList'].append(dev)

            # 测试
            qa = {
                "clusterType": '测试',
                "runningCount": runningCount_qa,
                "successCount": successCount_qa,
                "failedCount": failedCount_qa,
                "deployCount": deployCount_qa,
                "deployManualCount": deployManualCount_qa,
                "deployStrategyCount": deployStrategyCount_qa,
                "timeConsume": 0,

            }
            if num_qa != 0:
                qa['timeConsume'] = round(timeConsume_qa / num_qa, 2)

            ret['clusterInfoList'].append(qa)

            # 预发布
            uat = {
                "clusterType": '预发布',
                "runningCount": runningCount_uat,
                "successCount": successCount_uat,
                "failedCount": failedCount_uat,
                "deployCount": deployCount_uat,
                "deployManualCount": deployManualCount_uat,
                "deployStrategyCount": deployStrategyCount_uat,
                "timeConsume": 0,

            }
            if num_uat != 0:
                uat['timeConsume'] = round(timeConsume_uat / num_uat, 2)

            ret['clusterInfoList'].append(uat)


            return ret

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
