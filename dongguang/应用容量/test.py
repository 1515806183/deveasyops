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
# 搜索所有实例数据的ID
search_model = 'BUSINESS'

# 搜索实列列表条件
ConfigParams = {"query": {}, "fields": {"instanceId": True, "name": True, "_businesses_APP": True, "HOST": True},
                "only_relation_view": True, "only_my_instance": False}


# Easyops查询实例
class EasyopsPubic(object):
    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        return self.instance_search(search_model, ConfigParams)

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
        if method in ('dc_console',):
            url = restful_api
            headers['host'] = 'dc_console.easyops-only.com'
        else:
            url = "http://{easy_host}{restful_api}".format(easy_host=easyops_cmdb_host, restful_api=restful_api)
            headers['host'] = easy_domain

        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        # 获取监控指标数据
        elif method in ('dc_console',):
            try:
                r = requests.get(url=url, headers=headers, data=params)
                if r.status_code == 200:
                    return json.loads(r.content)['results']
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

    def gevent_data(self, i):
        # 取应用系统信息
        bus_instanceId = i.get('instanceId')
        bus_name = i.get('name')
        # 取APP数量
        appDataList = i.get('_businesses_APP')
        app_nums = len(appDataList)
        # 取主机数量和ip
        hostDataList = i.get('HOST')
        host_nums = len(hostDataList)
        host_ip_list = []  # ip为K， id为V
        if hostDataList:
            for ip in hostDataList:
                host_ip = ip.get('ip')
                host_ip_list.append({host_ip: []})

        # 循环主机列表， 获取单个主机的指标
        inser_host_data = []
        if host_ip_list:
            for ip_data in host_ip_list:
                host_ip = ip_data.keys()[0]
                ip = str(host_ip).split('.')

                # cpu使用率
                cpu_url = "http://" + easyops_cmdb_host + """:8087/api/v1/influxdb/proxy/query?db=easyops&q=SELECT last("host.mem.percent") FROM "host"."host" WHERE ("ip" =~ /^""" + str(
                    ip[0]) + """\.""" + str(ip[1]) + """\.""" + str(ip[2]) + """\.""" + str(
                    ip[3]) + """$/) AND time >= now() - 1h&epoch=ms """
                cpu_ret = self.easyopsObj.http_post('dc_console', cpu_url)

                # 内存使用率
                mem_url = "http://" + easyops_cmdb_host + """:8087/api/v1/influxdb/proxy/query?db=easyops&q=SELECT last("host.mem.percent") FROM "host"."host" WHERE ("ip" =~ /^""" + str(
                    ip[0]) + """\.""" + str(ip[1]) + """\.""" + str(ip[2]) + """\.""" + str(
                    ip[3]) + """$/) AND time >= now() - 1h&epoch=ms """

                men_ret = self.easyopsObj.http_post('dc_console', mem_url)

                # 磁盘使用率
                disk_url = "http://" + easyops_cmdb_host + """:8087/api/v1/influxdb/proxy/query?db=easyops&q=SELECT last("host.disk.max_used_percent") FROM "host"."host" WHERE ("ip" =~ /^""" + str(
                    ip[0]) + """\.""" + str(ip[1]) + """\.""" + str(ip[2]) + """\.""" + str(
                    ip[3]) + """$/) AND time >= now() - 1h&epoch=ms """

                disk_ret = self.easyopsObj.http_post('dc_console', disk_url)
                try:
                    cpu = str(cpu_ret[0]['series'][0]['values'][0][-1]) + '%'
                except:
                    cpu = '0%'

                try:
                    mem = str(men_ret[0]['series'][0]['values'][0][-1]) + '%'
                except:
                    mem = '0%'
                try:
                    disk = str(disk_ret[0]['series'][0]['values'][0][-1]) + '%'
                except:
                    disk = '0%'
                data = {
                    "ip": host_ip,
                    "cpu_user": cpu,
                    "mem_user": mem,
                    "disk_user": disk
                }
                inser_host_data.append(data)
        data = {
            "keys": ['name', ],
            "datas": [{
                "name": bus_name,
                "app_nums": str(app_nums),
                "host_nums": str(host_nums),
                "utilization_rate": inser_host_data
            }]
        }

        # 插入数据到模型
        if len(data['datas']):
            info_url = "/object/{0}/instance/_import".format('app_capacity')
            res = self.easyopsObj.http_post('many_post', info_url, data)
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
