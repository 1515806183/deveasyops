# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey

monkey.patch_all()
import gevent
from gevent.pool import Pool

# CMDB配置
easyops_cmdb_host = '172.18.208.13'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索所有实例数据的ID
ConfigSWITCHMODEL = '_SWITCH'

# 搜索实列列表条件
ConfigParams = {
    "query": {
        "idc_type": {"$eq": "寮步"},
        "cdp_cisco": {"$eq": "yes"},

    },
    "fields": {
        "community": True,
        "ip": True,
        "sysName": True
    }}

cisco_oid = {
    'vmVlan': '.1.3.6.1.4.1.9.9.68.1.2.2.1.2',
    'cdpCacheSysName': '1.3.6.1.4.1.9.9.23.1.2.1.1.6',
    'cdpCachePortName': '1.3.6.1.4.1.9.9.23.1.2.1.1.7',
    'cdpCacheType': '1.3.6.1.4.1.9.9.23.1.2.1.1.3',
    'cdpCacheIP': '1.3.6.1.4.1.9.9.23.1.2.1.1.4',
    'IfDescr': '1.3.6.1.2.1.2.2.1.2'
}

dot_oid = {
    'dot1dBasePortIfIndex': '1.3.6.1.2.1.17.1.4.1.2',
    'dot1qTpFdbPort': '1.3.6.1.2.1.17.4.3.1.2',
    'dot1qTpFdbMac': '1.3.6.1.2.1.17.4.3.1.1',
}

run_timeout = 3


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

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    print r.content
                    return json.loads(r.content)
            except Exception as e:
                print e
                return {"list": []}


class ThreadInsert(object):
    def __init__(self):
        self.datas = {}
        self.pool = Pool(20)
        start_time = time.time()
        self.data = self.getData()
        self.ciscoobj = CiscoClear()
        self.task()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        self.easyopsObj = EasyopsPubic()
        data = self.easyopsObj()
        n = 2  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data[i:i + n] for i in range(0, len(data), n)]
        return result

    def dealdata(self, content):
        # 开个携程池玩玩
        res = []
        for data_info in content:
            ip = data_info.get('ip')
            name = data_info.get('sysName')
            community = data_info.get('community')
            for key, oid in cisco_oid.items():
                res.append(
                    self.pool.spawn(self.task_gevent, "snmpwalk -v 2c -c {0} {1} {2}".format(community, ip, oid), key,
                                    ip, community, name))

        gevent.joinall(res)
        # 遍历获取返回值
        dataList = {}
        # 清洗数据到集合中
        for v in res:
            for key, val in v.value.items():
                if not dataList.has_key(key):
                    dataList[key] = []
                dataList[key].append(val)
        for key, val in dataList.items():
            if not self.datas.has_key(key):
                self.datas[key] = {}
            for i in val:
                for k, v in i.items():
                    res = getattr(self.ciscoobj, k)(v)
                    self.datas[key].update(res)
        # 开始处理数据
        self.deal_data()

    def deal_data(self):
        # cdp采集对端设备
        inser_data = {
            "keys": ['name', ],
            "datas": [
            ]
        }

        for key, data in self.datas.items():
            # key 是当前设备名
            ifDescr = self.datas[key].get('ifDescr')
            key = key.split('&&')[0]
            # 对端信息
            names = data.get('name')
            peer_type = data.get('peer_type')
            peer_device = data.get('peer_device')
            for k, v in names.items():
                # 当前设备交换机端口名,根据key 合并成唯一标识名
                only_name = key + ':' + ifDescr.get(str(k))

                # 组合对端设备信息, v是端口名
                type = peer_type[k]  # 对端类型
                device = peer_device[k]  # 对端设备
                name = device + ":" + v  # 对端端口名
                info = {
                    "name": name,
                    "peer_type": str(type),
                    "peer_device": str(device),
                    "peer_port": str(v),

                }
                inser_data['datas'].append({
                    'name': only_name,
                    "remote_list": [info]
                })
        # 汇报了对端信息，
        url = "/object/{0}/instance/_import".format("NETDPORT")
        self.easyopsObj.http_post("many_post", url, inser_data)

        # 处理mac_table,邻居信息
        cms = []
        for key, data in self.datas.items():
            info_list = key.split('&&')
            ip = info_list[1]
            community = info_list[2]
            vlan_list = data.get('vlan', '')
            if vlan_list:
                for vlan in vlan_list:
                    for oid_k, oid_v in dot_oid.items():
                        cmd = "snmpwalk -v 2c -c {0} {1} {2}".format(community + "@" + str(vlan), ip, oid_v)
                        cms.append(cmd)
        n = 2  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [cms[i:i + n] for i in range(0, len(cms), n)]

        try:
            q = Queue(maxsize=10)
            while result:
                content = result.pop()
                t = threading.Thread(target=self.deal_valn, args=(content,))
                q.put(t)
                if (q.full() == True) or (len(result)) == 0:
                    thread_list = []
                    while q.empty() == False:
                        t = q.get()
                        thread_list.append(t)
                        t.start()
                        for t in thread_list:
                            t.join()
        except Exception as e:
            print e

    def deal_valn(self, content):
       print content

    def task_gevent(self, cmd, key, ip, community, name):
        # 携程执行单个snmp任务
        key_name = name + "&&" + ip + "&&" + community
        # 开始执行snmp任务
        try:
            data = self._run_command(cmd, timeout=run_timeout)
        except subprocess.CalledProcessError as e:
            data = ''
        except Exception as e:
            data = ''
        return {key_name: {key: data}}

    def _run_command(self, cmd, timeout=60):
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

    # 开启多线程任务
    def task(self):
        # 设定最大队列数和线程数
        try:
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
        except Exception as e:
            print e


# 思科根据OID采集数据
class CiscoClear():
    # vlan
    def vmVlan(self, data):
        result = {}
        vlan_list = re.findall(r'.9.9.68.1.2.2.1.2.\d+ = INTEGER:\s+(\d+)', data)
        vlan = set()
        if vlan_list:
            for i in vlan_list:
                get_vlan = i.split(" ")[-1]
                try:
                    get_vlan = int(get_vlan)
                    if get_vlan:
                        vlan.add(str(get_vlan))
                except:
                    pass

        result['vlan'] = list(vlan)
        return result

    # 对端ip
    def cdpCacheIP(self, data):
        serial_dict = {
            "peer_ip": {}
        }
        # 判断是否真的采集
        if 'No Such' not in data:
            for i in str(data).split('\n'):
                if i:
                    serial = re.search(r'9.9.23.1.2.1.1.4.(\d+).\d+\s+=\s+Hex-STRING:\s+(.*)', i)
                    num = serial.group(1)  # 10101 10102
                    integer = serial.group(2)  # C0 A6 FE F5

                    one_data = {num: integer}
                    serial_dict['peer_ip'].update(one_data)

        return serial_dict

    # 对端端口名称
    def cdpCachePortName(self, data):
        serial_dict = {
            "name": {}
        }

        # 判断是否真的采集
        if 'No Such' not in data:
            for i in str(data).split('\n'):
                if i:
                    serial = re.search(r'9.9.23.1.2.1.1.7.(\d+).\d+\s+=\s+STRING:\s+(.*)', i)
                    num = serial.group(1)  # 10101 10102
                    string = eval(serial.group(2))  # GigabitEthernet0

                    one_data = {num: string}

                    serial_dict['name'].update(one_data)

        return serial_dict

    # 对端设备名称
    def cdpCacheSysName(self, data):
        """
        10111 AP05
        :param data:
        :return:
        """
        serial_dict = {
            "peer_device": {}
        }

        # 判断是否真的采集
        if 'No Such' not in data:
            for i in str(data).split('\n'):
                if i:
                    serial = re.search(r'9.9.23.1.2.1.1.6.(\d+).\d+\s+=\s+STRING:\s+(.*)', i)
                    num = serial.group(1)  # 10101 10102
                    string = eval(serial.group(2))  # AP03 AP04
                    one_data = {num: string}
                    serial_dict['peer_device'].update(one_data)

        return serial_dict

    # 对端设备类型
    def cdpCacheType(self, data):
        serial_dict = {
            "peer_type": {}
        }

        # 判断是否真的采集
        if 'No Such' not in data:
            for i in str(data).split('\n'):
                if i:
                    serial = re.search(r'9.9.23.1.2.1.1.3.(\d+).\d+\s+=\s+INTEGER:\s+(.*)', i)
                    num = serial.group(1)  # 10101 10102
                    integer = eval(serial.group(2))  # 1

                    one_data = {num: integer}

                    serial_dict['peer_type'].update(one_data)
        return serial_dict

    def IfDescr(self, data):
        IfDescrList = re.findall(r'IF-MIB::ifDescr.(.*)', data)
        result_list = {}
        for descr in IfDescrList:
            res_list = descr.split(' ')
            result_list.update({res_list[0]: res_list[-1]})
        return {"ifDescr": result_list}


if __name__ == '__main__':
    ThreadInsert()
