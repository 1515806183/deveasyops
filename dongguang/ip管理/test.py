# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re, IPy
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


# Easyops查询实例
class EasyopsPubic(object):
    def __init__(self, search_model, search_params):
        self.search_model = search_model
        self.search_params = search_params

    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        return self.instance_search(self.search_model, self.search_params)

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
            raise Exception('没有查询到数据')

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
        self.easyopsObj = EasyopsPubic('IPSCOPER', {"fields": {"instanceId": True, "name": True}})
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
        # 开始执行shell命令，查询ip
        cmd = 'nmap -nsP --host-timeout 10 %s' % str(i.get('name'))
        # 开始执行snmp任务
        try:
            data = self._run_command(cmd)
        except subprocess.CalledProcessError as e:
            data = ''
        except Exception as e:
            data = ''

        # 清洗数据
        self._deal_data(data, i)

    def _deal_data(self, data, ip_data):
        """
        :param data: 单条网段采集后的数据
        :param ip_data: 单个网段数据
        :return:
        """
        if data:
            # 1. 判断是否取到了ip
            try:
                ip_nums = re.search(r'\((\d+) hosts up\)', data).group(1)
            except Exception as e:
                ip_nums = 0

            # 2. 判断取到的ip数量，如果有，再次正则取所有的数据
            inser_data = {
                "keys": ['name', ],
                "datas": []
            }
            if int(ip_nums) > 0:
                ip_list = re.findall(r'Nmap scan report for\s+(.*)', data)
                for ip in ip_list:
                    data = {
                        "name": ip,  # IP地址
                        "status": "已分配",
                        "type": "生产",  # 性质
                        "is_black": "黑IP",
                        "IPSCOPER": ip_data.get('instanceId')  # 设置关系
                    }
                    inser_data['datas'].append(data)

            if len(inser_data['datas']):
                info_url = "/object/{0}/instance/_import".format('IPADDRESS')
                res = self.easyopsObj.http_post('many_post', info_url, inser_data)
                print res

        else:
            pass

    def _run_command(self, cmd, timeout=15):
        """执行命令cmd，返回命令输出的内容。
        如果超时将会抛出TimeoutError异常。
        cmd - 要执行的命令
        timeout - 最长等待时间，单位：秒
        """
        p = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
        t_beginning = time.time()
        while True:
            if p.poll() is not None:
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                # 记录超时的机器ip
                return ''
            time.sleep(0.1)
        return p.stdout.read()

    def _getHost(self):
        """
        :return: 返回所有的主机信息
        """
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('HOST', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            host_dict[host.get('ip')] = host.get('instanceId')

        return host_dict

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


class IpListInsert(object):
    def __init__(self):
        self.pool = Pool(40)
        start_time = time.time()
        self.data = self.getData()
        self.hostsdata = self._getHost()  # 主机
        self.FirewallData = self._getFirewall()  # 防火墙
        self.RoutesData = self._get_ROUTER()  # 路由器
        self.SwitchsData = self._get_SWITCH()  # 交换机
        self.vmhostData = self._get_vmhost()  # 宿主机
        self.vmhvirtualData = self._get_vmhvirtual()  # 虚拟机
        self.securityData = self._get_security()  # 安全系统
        self.outbandData = self._get_outband()  # 带外
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        st = time.time()
        self.easyopsObj = EasyopsPubic('IPSCOPER', {"fields": {"instanceId": True, "name": True, "IPADDRESS": True}})
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

    def _inser_data(self, i, selfobj, useobj, model, name):
        """
        :param i: 单个ip网段下面的ip
        :param selfobj: 获取到的模型的所有实例
        :param useobj: 属性
        :param model: 关联模型别名
        :param name: print
        :return:
        """
        IPADDRESS = i.get('IPADDRESS', '')
        if IPADDRESS:
            inser_data = {
                "keys": ['name'],
                "datas": []
            }
            ip_segment = i.get('name')  # 网段
            for ip in selfobj.keys():
                # 判断主机IP是否在这个网段里面，如果存在，找到对应的ip，关联主机模型
                if ip in IPy.IP(ip_segment):
                    for data in IPADDRESS:
                        ipaddr = data.get('name')
                        if ip == ipaddr:
                            # 取到ip地址的ip实例
                            res = {
                                "name": ipaddr,
                                "is_black": "不是黑IP",
                                "useobj": useobj,
                                model: selfobj[ip]
                            }
                            inser_data['datas'].append(res)

            if len(inser_data['datas']):
                info_url = "/object/{0}/instance/_import".format('IPADDRESS')
                res = self.easyopsObj.http_post('many_post', info_url, inser_data)
                print str(name) + str(res)

    def gevent_data(self, i):
        # 关联主机
        self._inser_data(i, self.hostsdata, "主机", 'HOST', "主机: ")

        # 关联防火墙
        self._inser_data(i, self.FirewallData, "防火墙", 'FIREWALL', "防火墙: ")

        # 关联路由器
        self._inser_data(i, self.RoutesData, "路由器", 'ROUTER', "路由器: ")

        # 关联交换机
        self._inser_data(i, self.SwitchsData, "交换机", 'SWITCH', "交换机: ")

        # 关联宿主机
        self._inser_data(i, self.vmhostData, "宿主机", 'VMWARE_HOST_COMPUTER', "宿主机: ")

        # 关联VM虚拟机
        self._inser_data(i, self.vmhvirtualData, "VM虚拟机", 'VMWARE_VIRTUAL_MACHINE', "VM虚拟机: ")

        # 关联安全系统
        self._inser_data(i, self.securityData, "安全设备", 'SECURITY_SYSTEM', "安全设备: ")

        # 关联带外
        self._inser_data(i, self.outbandData, "带外", 'OUT_OF_BAND_MANAGEMENT', "带外: ")

    def _get_outband(self):
        sear_host = {"fields": {"instanceId": True, "businessIP": True}}
        ret = self.easyopsObj.instance_search('OUT_OF_BAND_MANAGEMENT', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('businessIP')
            if ip:
                host_dict[ip] = host.get('instanceId')
        return host_dict

    def _get_security(self):
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('SECURITY_SYSTEM', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ip')
            if ip:
                host_dict[ip] = host.get('instanceId')
        return host_dict

    def _get_vmhvirtual(self):
        """
        :return:
        """
        sear_host = {"fields": {"instanceId": True, "default_ip_address": True}}
        ret = self.easyopsObj.instance_search('VMWARE_VIRTUAL_MACHINE', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('default_ip_address')
            if ip:
                host_dict[ip] = host.get('instanceId')
        return host_dict

    def _get_vmhost(self):
        """
        :return:
        """
        sear_host = {"fields": {"instanceId": True, "ipaddr": True}}
        ret = self.easyopsObj.instance_search('VMWARE_HOST_COMPUTER', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ipaddr')
            if ip:
                host_dict[ip] = host.get('instanceId')
        return host_dict

    def _get_SWITCH(self):
        """
        :return: 返回所有交换机器信息
        """
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('_SWITCH', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ip')
            if ip:
                host_dict[ip] = host.get('instanceId')

        return host_dict

    def _get_ROUTER(self):
        """
        :return: 返回所有路由器信息
        """
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('_ROUTER', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ip')
            if ip:
                host_dict[ip] = host.get('instanceId')

        return host_dict

    def _getFirewall(self):
        """
        :return: 返回所有防火墙信息
        """
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('_FIREWALL', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ip')
            if ip:
                host_dict[ip] = host.get('instanceId')

        return host_dict

    def _getHost(self):
        """
        :return: 返回所有的主机信息
        """
        sear_host = {"fields": {"instanceId": True, "ip": True}}
        ret = self.easyopsObj.instance_search('HOST', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('ip')
            if ip:
                host_dict[ip] = host.get('instanceId')

        return host_dict

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


class OutBand(object):
    def __init__(self):
        self.pool = Pool(40)
        start_time = time.time()
        self.data = self.getData()
        self.oubtbandmanageData = self._get_outbandmanage()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

    # 从本地的文件中读取数据
    def getData(self):
        st = time.time()
        self.easyopsObj = EasyopsPubic('IPSCOPER',
                                       {"fields": {"instanceId": True, "name": True, "IPADDRESS": True}})  # 网段
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
        ip_scoper_name = i.get('name')  # ip网段标识
        inser_list = []

        for ip in self.oubtbandmanageData:
            if ip in IPy.IP(ip_scoper_name):
                # 只要ip在这个网段内就增加带外管理关系，修改或者新增
                res = {
                    "name": ip,
                    "is_black": "不是黑IP",
                    "useobj": '带外管理',
                    'OUT_OF_BAND_MANAGEMENT_': self.oubtbandmanageData[ip],  # 关系带外管理模型
                    "IPSCOPER": i.get('instanceId') # 网段ID
                }
                inser_list.append(res)

        if inser_list:
            inser_data = {
                "keys": ['name'],
                "datas": inser_list
            }

            if len(inser_data['datas']):
                info_url = "/object/{0}/instance/_import".format('IPADDRESS')  # IP模型ID
                res = self.easyopsObj.http_post('many_post', info_url, inser_data)
                print str('带外管理：') + str(res)

    # 带外管理IP单独处理
    def _get_outbandmanage(self):
        sear_host = {"fields": {"instanceId": True, "outOfBandIP": True}}
        ret = self.easyopsObj.instance_search('OUT_OF_BAND_MANAGEMENT', sear_host)
        # 以ip:实例ID组合字典
        host_dict = {}
        for host in ret:
            ip = host.get('outOfBandIP')
            if ip:
                host_dict[ip] = host.get('instanceId')
        return host_dict

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
    # ThreadInsert() # 扫描网段
    # 获取所有的IP
    # IpListInsert()
    OutBand()
