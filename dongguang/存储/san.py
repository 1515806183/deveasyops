# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re, paramiko, warnings
import threading
from Queue import Queue
from paramiko import SSHClient
from gevent import monkey

monkey.patch_all()
import gevent
from gevent.pool import Pool
import sys

reload(sys)
sys.setdefaultencoding('utf-8')

# CMDB配置
easyops_cmdb_host = '172.18.208.13'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

# 查询条件
# 搜索所有实例数据的ID
ConfigSWITCHMODEL = 'STORASWITCH'

# 搜索实列列表条件
ConfigParams = {
    "query": {
        "autoCollect": {"$eq": "lb_yes"},
    },
    "fields": {
        "name": True,
        "ip": True,
        "username": True,
        "password": True,
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


# ssh 连接
class ParamikoConn(object):
    def __init__(self, user, passwd, ip, port=22):
        self.user = user
        self.passwd = passwd
        self.ip = ip
        self.port = port
        self.ssh = SSHClient()

    def run_cmd(self, cmd):
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.ip, self.port, self.user, self.passwd, timeout=60)
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        result = stdout.readlines()
        return result

    def close(self):
        self.ssh.close()


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
        n = 1  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data[i:i + n] for i in range(0, len(data), n)]
        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    # 下面是ssh采集数据

    # 下面是汇报数据
    # 采集基本信息，并汇报
    def __post_info(self, ssh, name, version, psshow_data, temp, fans, Mem):
        info_data = []  # 盘柜信息
        info_res = self.__get_info(ssh, version)
        info_data.append(
            {"name": name, "info": info_res, "psshow_data": psshow_data, "temp": temp, "fans": fans, "Mem": Mem})

        # -------------------------- 获取基本信息完
        # 汇报基本信息
        info = {
            "keys": ["name"],
            "datas": info_data
        }

        if len(info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORASWITCH')
            res = self.easyopsObj.http_post('many_post', info_url, info)
            print '基本采集完成:', res
        return info_data

    # 采集端口信息，并汇报
    def __post_port(self, ssh, san_name):
        '''
            获取SAN交换机端口的信息
            :param cls:
            :return:
            '''
        """获取san端口信息"""
        port_list = []
        config_cmd = 'switchshow'
        config_info = ssh.run_cmd(config_cmd)
        config_list = []
        for info in config_info:
            info = info.split()
            config_list.append(info)
        while [] in config_list:
            config_list.remove([])
        port_temps = config_list[16:]

        temp_list = []
        # print 'port temps_for_debug',port_temps
        for temps in port_temps:
            temp_list.append(temps[0])
        # print 'temps_for_debug',temp_list
        # 获取端口的详细信息
        for index in temp_list:
            port_cmd = 'portshow ' + '-i ' + index
            # print 'port cmd _for_debug',port_cmd
            port_info = ssh.run_cmd(port_cmd)
            # print 'port info _for_debug',port_info
            port_id = port_type = port_state = port_speed = port_index = port_name = port_wwn = ''
            wwn_list = []
            for info in port_info:
                # print 'info _for_debug',info
                if re.search(r"portId:\s*(.*)", info, re.I):
                    port_id = re.search(r"portId:\s*(.*)", info, re.I).group(1)
                if re.search(r"portType:\s*(.*)", info, re.I):
                    port_type = re.search(r"portType:\s*(.*)", info, re.I).group(1)
                if re.search(r"portState:\s*(.*)", info, re.I):
                    port_state = re.search(r"portState:\s*(.*)", info, re.I).group(1)
                if re.search(r"portSpeed:\s*(.*)", info, re.I):
                    port_speed = re.search(r"portSpeed:\s*(.*)", info, re.I).group(1)
                if re.search(r"portIndex:\s*(.*)", info, re.I):
                    port_index = re.search(r"portIndex:\s*(.*)", info, re.I).group(1)
                if re.search(r"portName:\s*(.*)", info, re.I):
                    port_name = re.search(r"portName:\s*(.*)", info, re.I).group(1)
                if re.search(r"portWwn:\s*(.*)", info, re.I):
                    port_wwn = re.search(r"portWwn:\s*(.*)", info, re.I).group(1)
                if re.search(r"[\s\S]\s*(\w+:\w+:\w+:\w+:\w+:\w+:\w+:\w+)", info, re.I):
                    rel_wwn = re.search(r"(\w+:\w+:\w+:\w+:\w+:\w+:\w+:\w+)", info, re.I).group(1)
                    if rel_wwn == port_wwn:
                        continue
                    else:
                        wwn_list.append(rel_wwn)

            port_dict = {
                'name': san_name + ":" + port_id,
                'type': port_type,
                'status': port_state,
                'speed': port_speed,
                'portindex': port_index,
                'port_name': port_name,
                'device_port_wwn': port_wwn,
                # 'port_num': port,
                'rel_wwn': wwn_list
            }
            port_list.append(port_dict)

        return port_list

    # 采集基本信息 sfabricshow
    def __get_info(self, ssh, version):
        try:
            datas = ssh.run_cmd('fabricshow')
            # with open('./san/fabricshow') as f:
            #     datas = f.readlines()
        except Exception as e:
            print e
            print u'解析基本信息错误'
        try:
            info_list = []
            # 默认走寮步基本信息处理
            # 1: fffc01 10:00:88:94:71:a7:ea:8d 18.18.200.7     0.0.0.0        >"lb_f48_03"
            for data in datas[-3].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if rignt_data[0] in "|Pos" or '---' in rignt_data[0]:
                    continue

                id = rignt_data[0].split(':')[0]
                WorldwideName = rignt_data[1] + " " + rignt_data[2]
                FC_IP_Addr = rignt_data[4]
                os_name = rignt_data[5]

                res = {
                    "id": id,
                    "WorldwideName": WorldwideName,
                    "FC_IP_Addr": FC_IP_Addr,
                    "os_name": os_name.split('"')[1],
                    "version": version
                }
                info_list.append(res)

            # 如果为空，那就ssh基本信息
            if not info_list:
                for data in datas[-2].split('\n'):
                    rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                    if len(data) <= 2: continue
                    clean_data = data.split('\n')[0].split(' ')

                    # 去掉空白
                    for sprit in clean_data:
                        if sprit: rignt_data.append(sprit)
                    # [u'1:', u'fffc01', u'10:00:00:05:33:41:bf:80', u'20.20.200.225', u'0.0.0.0', u'>"B40_225"']
                    # 去掉第一个名字开头
                    if rignt_data[0] in "|Pos" or '---' in rignt_data[0]:
                        continue

                    id = rignt_data[0]
                    WorldwideName = rignt_data[1] + " " + rignt_data[2]
                    FC_IP_Addr = rignt_data[4]
                    os_name = rignt_data[5]

                    res = {
                        "id": id.split(":")[0],
                        "WorldwideName": WorldwideName,
                        "FC_IP_Addr": FC_IP_Addr,
                        "os_name": os_name.split('"')[1],
                        "version": version
                    }
                    info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理基本信息错误'

    # 采集固件版本信息 并汇报,firmwareshow
    def __post_versions(self, ssh, name):
        try:
            datas = ssh.run_cmd('firmwareshow')
            # with open('./san/firmwareshow') as f:
            #     datas = f.readlines()
            version = datas[-1].split(' ')[-1]
            return version

        except Exception as e:
            print e
            print u'固件版本信息错误'

    # 采集电源状态
    def __post_psshow(self, ssh):
        try:
            datas = ssh.run_cmd('psshow')
            # with open('./san/psshow') as f:
            #     datas = f.readlines()

            res = []
            for ps in datas[1:]:
                data = ps.split(' ')
                id = data[2]
                status = data[-1]
                res.append({"id": id, "status": status})
            return res

        except Exception as e:
            print e
            print u'电源状态信息错误'

    # 采集温度
    def __post_tempshow(self, ssh):
        try:
            datas = ssh.run_cmd('tempshow')
            # with open('./san/tempshow') as f:
            #     datas = f.readlines()

            data_list = []
            for data in datas[3:]:
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                data = data.split(' ')
                for sprit in data:
                    if sprit: rignt_data.append(sprit)

                id = rignt_data[0].split('\t')[0]
                status = rignt_data[0].split('\t')[1]
                Centigrade = rignt_data[2] + ' 摄氏度'  #

                data = {
                    "id": id,
                    "status": status,
                    "Centigrade": Centigrade,
                }
                data_list.append(data)

            return data_list

        except Exception as e:
            print e
            print u'温度信息错误'

    # 采集风扇信息
    def __post_fanshow(self, ssh):
        try:
            datas = ssh.run_cmd('fanshow')
            # with open('./san/fanshow') as f:
            #     datas = f.readlines()

            data_list = []
            for data in datas:
                fans = data.split(' ')
                id = fans[1]
                status = fans[3].split(',')[0]
                speed = fans[-2]
                data_list.append({
                    "id": id,
                    "status": status,
                    "speed": speed,
                })
            return data_list

        except Exception as e:
            print e
            print u'风扇信息错误'

    # 内存信息
    def __post_memshow(self, ssh):
        try:
            datas = ssh.run_cmd('memshow')
            # with open('./san/memshow') as f:
            #     datas = f.readlines()
            datas = datas[1].split('Mem:')[1].split(' ')

            datas = [i for i in datas if len(i) > 0]

            data_list = []
            total = datas[0]
            used = datas[1]
            free = datas[2]
            shared = datas[3]
            buffers = datas[4]
            cached = datas[5]

            data_list.append({
                "total": str(round(float(total) / 1024 / 1024, 2)) + ' GB',
                "used": str(round(float(used) / 1024 / 1024, 2)) + ' GB',
                "free": str(round(float(free) / 1024 / 1024, 2)) + ' GB',
                "shared": str(round(float(shared) / 1024 / 1024, 2)) + ' GB',
                "buffers": str(round(float(buffers) / 1024 / 1024, 2)) + ' GB',
                "cached": str(round(float(cached) / 1024 / 1024, 2)) + ' GB',
            })

            return data_list

        except Exception as e:
            print e
            print u'内存信息错误'

    def dealdata(self, content):
        for data in content:
            name = data.get("name")
            ip = data.get('ip')
            username = data.get('username')
            password = data.get('password')
            # 初始化ssh
            ssh = ParamikoConn(user=username, passwd=password, ip=ip)

            # 获取固件版本 firmwareshow
            # version = self.__post_versions(ssh, name)

            # 获取电源状态
            # psshow_data = self.__post_psshow(ssh)

            # 温度情况
            # temp = self.__post_tempshow(ssh)

            # 风扇信息
            # fanshow = self.__post_fanshow(ssh)

            # 内存信息
            # Mem = self.__post_memshow(ssh)

            # 基本信息信息，并汇报，info_data
            # info_data = self.__post_info(ssh, name, version, psshow_data, temp, fanshow, Mem)

            # 采集端口基本信息，并汇报
            port_dat = self.__post_port(ssh, name)

            ssh.close()

    # 去重
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
    # 屏蔽告警
    warnings.filterwarnings('ignore')
    ThreadInsert()
