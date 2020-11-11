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
ConfigSWITCHMODEL = 'STORAGE_DEVICE'

# 搜索实列列表条件
ConfigParams = {
    "query": {
        "collection_type": {"$eq": "3par"},
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
    # 基本信息 showsys
    def __info_data(self, ssh):
        try:
            # 先采集基本信息，uuid, 制造商  showsys
            datas = ssh.run_cmd('showsys')
            #with open('./3par/showsys') as f:
            #   datas = f.readlines()

            info_list = []
            for data in datas:
                rignt_data = []  # 这个保存清理完空格的数据
                clean_data = data.split('\n')[0].split(' ')
                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)
                    # 去掉第一个名字开头
                if rignt_data[0] == 'ID' or "---" in rignt_data[0] or len(rignt_data) == 0:
                    continue
                name = rignt_data[1]
                product_name = rignt_data[2] + " " + rignt_data[3]
                sn = rignt_data[4]
                total_vdisk_capacity = rignt_data[8]  # 总容量
                total_used_capacity = rignt_data[9]  # 使用容量
                total_free_space = rignt_data[10]  # 剩余容量

                res = {
                    "id_alias": name,
                    "product_name": product_name,
                    "sn": sn,
                    "total_vdisk_capacity": str(round(float(total_vdisk_capacity) / 1024 / 1024, 2)) + "TB",
                    "total_used_capacity": str(round(float(total_used_capacity) / 1024 / 1024, 2)) + "TB",
                    "total_free_space": str(round(float(total_free_space) / 1024 / 1024, 2)) + "TB",
                }
                info_list.append(res)

            return info_list

        except Exception as e:
            print e

    # 控制器信息 shownode
    def __get_enclosure(self, ssh):
        datas = ssh.run_cmd('shownode')
        #with open('./3par/shownode') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)

            # 去掉第一个名字开头
            if rignt_data[0] in ["Control", "Node"]:
                continue

            id = rignt_data[0]
            name = rignt_data[1]
            State = rignt_data[2]
            Master = rignt_data[3]
            Control_men = str(round(float(rignt_data[7]) / 1024, 2)) + "GB"
            Data_men = str(round(float(rignt_data[8]) / 1024, 2)) + "GB"
            Available = rignt_data[9].split('\r')[0] + "%"

            res = {
                "id": id,
                "name": name,
                "State": State,
                "Master": Master,
                "Control_men": Control_men,
                "Data_men": Data_men,
                "Available": Available,
            }
            info_list.append(res)

        return info_list

    # 电池信息 showbattery
    def __get_enclosure_battery(self, ssh):
        datas = ssh.run_cmd('showbattery')
        #with open('./3par/showbattery') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'Node':
                continue

            node_id = rignt_data[0].split(',')  # 关联的控制器id
            id = rignt_data[1]  # 电池ID
            Assem_Serial = rignt_data[3]  # sn
            State = rignt_data[4]  # 状态
            ChrgLvl = rignt_data[5] + "%"
            ExpDate = rignt_data[6]  # 出厂日期

            res = {
                "node_id": node_id,
                "id": id,
                "Assem_Serial": Assem_Serial,
                "State": State,
                "ChrgLvl": ChrgLvl,
                "ExpDate": ExpDate,
            }

            info_list.append(res)

        return info_list

    # 采集物理盘信息 showpd
    def __get_drive(self, ssh):
        datas = ssh.run_cmd('showpd')
        #with open('./3par/showpd') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if '----' in rignt_data[0] or 'Id' == rignt_data[0] or 'total' == rignt_data[1]:
                continue

            id = rignt_data[0]
            CagePos = rignt_data[1]
            Type = rignt_data[2]
            RPM = rignt_data[3]
            State = rignt_data[4]  # 状态
            Total = str(round(float(rignt_data[5]) / 1024, 2)) + "GB"  # 总空间
            Free = str(round(float(rignt_data[6]) / 1024, 2)) + "GB"  # 剩余空间
            Capacity = rignt_data[-1].split('\r')[0] + "GB"  # 磁盘容量

            res = {
                "id": id,
                "Type": Type,
                "RPM": RPM,
                "State": State,
                "Total": Total,
                "Free": Free,
                "Capacity": Capacity,
                "CagePos": CagePos,

            }
            info_list.append(res)

        return info_list

    # 采集逻辑盘信息  showld
    def __get_lds_info(self, ssh):
        datas = ssh.run_cmd('showld')
        # with open('./3par/showld') as f:
        #     datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split('\n\r')[0].split(' ')
            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头

            if "Id" in rignt_data[0] or len(rignt_data) <= 4:
                continue

            id = rignt_data[0]
            ld_name = rignt_data[1]
            RAID = rignt_data[2]
            Detailed_State = rignt_data[3]
            Own = rignt_data[4]
            SizeMB = str(rignt_data[5]) + " MB"
            UsedMB = str(rignt_data[6]) + " MB"

            res = {
                "id": id,
                "ld_name": ld_name,
                "RAID": RAID,
                "Detailed_State": Detailed_State,
                "Own": Own,
                "SizeMB": SizeMB,
                "UsedMB": UsedMB,
            }
            info_list.append(res)

        return info_list

    # 采集lun信息 showvlun
    def __get_lun_info(self, ssh):
        datas = ssh.run_cmd('showvlun')
        #with open('./3par/showvlun') as f:
        #    datas = f.read()
        index = datas.index('VLUN Templates\n')

        luns_host_data = {}  # luns和主机的关系
        for data in datas[:index]:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'Active' or rignt_data[0] == 'Lun':
                continue

            # 只取存储的luns， 模板不要
            if len(rignt_data) <= 1:
                break

            host_name = rignt_data[2]
            lun_id = rignt_data[0]
            if not luns_host_data.has_key(host_name):
                luns_host_data[host_name] = []

            luns_host_data[host_name].append(lun_id)  # 主机和lun信息

        luns_datas = []
        for data in datas[index+1:]:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split(' ')
            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if len(rignt_data) == 0 or rignt_data[0] == 'Lun':
                continue

            if 1 <= len(rignt_data) < 4:
                break

            # 只取存储的luns， 模板不要
            id = rignt_data[0]
            VVName = rignt_data[1]
            HostName = rignt_data[2]
            Type = rignt_data[-1]

            res = {
                "id": id,
                "VVName": VVName,
                "HostName": HostName,
                "Type": Type,
            }

            luns_datas.append(res)  # lun信息
        return luns_datas, luns_host_data

    # 下面是获取cmdb数据
    # 搜索主机实例
    def __search_hosts(self, luns_host_data):
        res_data = {}
        host_name_list = luns_host_data.keys()
        search_host = {
            "query": {
                "hostname": {"$in": host_name_list}
            },
            "fields": {
                "hostname": True
            }
        }

        host_list = self.easyopsObj.instance_search('HOST', search_host)
        for host in host_list:
            res_data.update({host.get('hostname'): host.get('instanceId')})

        return res_data

    # 搜索luns信息
    def __search_luns(self):
        res_data = {}
        search_host = {
            "fields": {
                "name": True,
                "id": True,
            }
        }

        host_list = self.easyopsObj.instance_search('STORAGELUN_PAR', search_host)
        for host in host_list:
            res_data.update({host.get('id'): host.get('name')})

        return res_data

    # 获取实例信息 盘柜,物理盘,逻辑盘,lun
    def __search_datas(self, modeld_id):
        res_data = {}
        search_parms = {
            "fields": {
                "name": True,
            }
        }

        res_list = self.easyopsObj.instance_search(modeld_id, search_parms)
        for res in res_list:
            instanceId = res.get('instanceId')
            name = res.get('name').split(':')[0]
            if not res_data.has_key(name):
                res_data[name] = []

            res_data[name].append(instanceId)

        return res_data


    # 下面是汇报数据
    # 采集基本信息，并汇报
    def ___post_infos(self, ssh, name):
        basic_data = []  # 基本信息
        info_data = self.__info_data(ssh)  # 处理基本信息
        basic_data.append({"name": name, "info_data": info_data})

        # 汇报基本数据信息
        basic_info = {
            "keys": ["name"],
            "datas": basic_data
        }

        if len(basic_info["datas"]):
            info_url = "/object/{0}/instance/_import".format(ConfigSWITCHMODEL)
            res = self.easyopsObj.http_post('many_post', info_url, basic_info)
            print '基本信息采集完成:', res

        return basic_data

    # 采集控制器，电源信息，并汇报
    def __post_enclosure(self, ssh, name):
        enclosure_data = []  # 盘柜信息
        enclosure_res = self.__get_enclosure(ssh)
        for res in enclosure_res:
            # 以存储设备名称 + ":" + id
            enclosure_name = str(name) + ':' + str(res.get('id'))
            res['name'] = enclosure_name
            enclosure_data.append(res)
        # -------------------------- 获取控制器信息完

        enclosure_battery_res = self.__get_enclosure_battery(ssh)
        for res in enclosure_battery_res:
            # 以存储设备名称 + ":" + id
            # 因为获取的node_id 是个list，
            node_id_list = res.get('node_id')
            for node_id in node_id_list:
                enclosure_battery_name = str(name) + ':' + str(node_id)
                for enclosure in enclosure_data:
                    if enclosure_battery_name == enclosure.get('name'):
                        if not enclosure.has_key('battery_res'):
                            enclosure['battery_res'] = []
                        enclosure['battery_res'].append(res)
                        break
        # -------------------------- 获取盘柜电池信息完

        # 汇报磁盘柜信息
        enclosure_info = {
            "keys": ["name"],
            "datas": enclosure_data
        }

        if len(enclosure_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_CABINET_PAR')
            res = self.easyopsObj.http_post('many_post', info_url, enclosure_info)
            print '磁盘柜信息采集完成:', res

        return enclosure_data

    # 采集物理盘信息，并汇报
    def __post_showpd(self, ssh, name):
        drive_data = []  # 物理盘信息
        drive_res = self.__get_drive(ssh)
        for res in drive_res:
            # 以存储设备名称 + ":" + id
            drive_name = str(name) + ':' + str(res.get('id'))
            res['name'] = drive_name
            drive_data.append(res)
        # -------------------------- 获取物理盘信息完

        # 汇报drive 物理盘信息
        drive_info = {
            "keys": ["name"],
            "datas": drive_data
        }

        if len(drive_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_PAR')
            res = self.easyopsObj.http_post('many_post', info_url, drive_info)
            print 'drive 硬盘信息采集完成:', res

        return drive_data

    # 采集逻辑盘，并汇报
    def __post_ld(self, ssh, name):
        lds_data = []  # lds 逻辑盘
        lds_res = self.__get_lds_info(ssh)
        for res in lds_res:
            # 以存储设备名称 + ":" + lun_name
            lds_name = str(name) + ':' + str(res.get('id'))
            res['name'] = lds_name
            lds_data.append(res)
        # -------------------------- 逻辑盘信息完

        # 汇报逻辑信息
        lun_info = {
            "keys": ["name"],
            "datas": lds_data
        }

        if len(lun_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_LD_PAR')
            res = self.easyopsObj.http_post('many_post', info_url, lun_info)
            print '逻辑盘信息采集完成:', res

        return lds_data

    # 采集lun，并汇报
    def __post_lun(self, ssh, name):
        lun_data = []  # lun

        lun_res, luns_host_data = self.__get_lun_info(ssh)  # lun信息 和 lun与主机信息
        for res in lun_res:
            # 以存储设备名称 + ":" + lun_name
            lun_name = str(name) + ':' + str(res.get('VVName')) + ":" + str(res.get('id'))
            res['name'] = lun_name
            lun_data.append(res)
        # -------------------------- LUN信息完
        # 汇报lun信息
        lun_info = {
            "keys": ["name"],
            "datas": lun_data
        }

        if len(lun_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGELUN_PAR')
            res = self.easyopsObj.http_post('many_post', info_url, lun_info)
            print 'lun信息采集完成:', res

        return lun_data, luns_host_data

    # 下面是设置关系
    # 设置lun 和主机关系
    def __set_luns_host(self, luns_host_data, luns_datas, host_instars):

        for host_name, luns_ids in luns_host_data.items():
            luns_ids = list(set(luns_ids))
            inser_data = {
                "keys": ['name'],
                "datas": []
            }
            inser = host_instars.get(host_name, [])
            if not inser: continue
            for id in luns_ids:
                if luns_datas.has_key(id):
                    lun_name = luns_datas[id]
                    res = {
                        "name": lun_name,
                        'HOST': inser
                    }

                    inser_data['datas'].append(res)
            if len(inser_data["datas"]):
                info_url = "/object/{0}/instance/_import".format('STORAGELUN_PAR')
                res = self.easyopsObj.http_post('many_post', info_url, inser_data)
                print 'LUN和主机关系:', res

    # 存储设备和lun,物理盘,逻辑盘,盘柜关系
    def __set_device_raps(self, enclosure_res, disk_res, ld_res, luns_res):
        # 盘柜和存储设备
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name, inses in enclosure_res.items():
            res = {
                "name": name,
                "DISK_CABINET_PAR": inses
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置盘柜和存储设备关系:', res

        # 物理盘和存储设备
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name, inses in disk_res.items():
            res = {
                "name": name,
                "DISK_PAR": inses
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置物理盘和存储设备关系:', res

        # 逻辑盘和存储设备
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name, inses in ld_res.items():
            res = {
                "name": name,
                "DISK_LD_PAR": inses
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置逻辑盘和存储设备关系:', res

        # luns和存储设备
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name, inses in luns_res.items():
            res = {
                "name": name,
                "STORAGELUN_PAR": inses
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置逻辑盘和存储设备关系:', res

    def dealdata(self, content):
        for data in content:
            name = data.get("name")
            ip = data.get('ip')
            username = data.get('username')
            password = data.get('password')
            # 初始化ssh
            ssh = ParamikoConn(user=username, passwd=password, ip=ip)

            # 采集基本信息，并汇报 basic_data
            self.___post_infos(ssh, name)

            # 盘柜，电池， 电源信息，并汇报，enclosure_data
            self.__post_enclosure(ssh, name)

            # 采集物理盘信息 并汇报， showpd
            self.__post_showpd(ssh, name)

            # 采集逻辑盘，并汇报，lds_data
            lds_data = self.__post_ld(ssh, name)

            # 采集lun，并汇报 showvlun
            lun_data, luns_host_data = self.__post_lun(ssh, name)

            ssh.close()

            # TODO 逻辑盘和物理盘,lun和物理盘关系没建立,因为运行脚本,服务器返回信息太慢了,逻辑盘数量太多
            # 汇报数据完成---- 设置关系做铺垫--------------------------------------------
            # 1. 设置lun和主机的关系
            # 1.1 先获取到主机名，根据主机名
            # host_instars = self.__search_hosts(luns_host_data)
            # 1.2 获取luns 信息
            # luns_datas = self.__search_luns()
            # 1.3设置主机和luns关系
            # self.__set_luns_host(luns_host_data, luns_datas, host_instars)

            # 2. lun和逻辑盘的关系
            # 2.1 先从lun里面获取vvname，排除带：的
            # for lun in lun_data:
            #    vvname = lun.get('VVName')
            #    if ':' in vvname: continue
            #    cmd = "showvvmap " + vvname
            #    ssh.run_cmd(cmd)
            #    print 1

            # 设置存储设备和盘柜, 物理盘,逻辑盘,lun关系
            # 1.1 获取盘柜信息
            enclosure_res = self.__search_datas('DISK_CABINET_PAR')
            # 1.2 获取物理盘信息
            disk_res = self.__search_datas('DISK_PAR')
            # 1.3 获取逻辑盘实例
            ld_res = self.__search_datas('DISK_LD_PAR')
            # 1.4 获取lun实例信息
            luns_res = self.__search_datas('STORAGELUN_PAR')

            # 跟存储设备建立关系
            self.__set_device_raps(enclosure_res, disk_res, ld_res, luns_res)

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
