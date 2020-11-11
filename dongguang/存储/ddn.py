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
        "collection_type": {"$eq": "DDN"},
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
        result = stdout.read()
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

    # 采集盘柜信息 show ENCLOSURE
    def __get_enclosure(self, ssh):
        datas = ssh.run_cmd('show ENCLOSURE')
        # with open('./ddn/ENCLOSURE') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx')[1].split('Total')
        except Exception as e:
            print e
            print u'解析盘柜信息错误'
        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if rignt_data[0] in "|Pos" or '---' in rignt_data[0]:
                    continue
                Idx = rignt_data[0]
                Pos = rignt_data[1]
                Type = rignt_data[2]
                Logical_ID = rignt_data[3]
                Vendor_ID = rignt_data[4]
                Product_ID = rignt_data[5]
                FW_Version = rignt_data[7]

                res = {
                    "Idx": Idx,
                    "Pos": Pos,
                    "Type": Type,
                    "Logical_ID": Logical_ID,
                    "Vendor_ID": Vendor_ID,
                    "Product_ID": Product_ID,
                    "FW_Version": FW_Version,
                }
                info_list.append(res)
            return info_list
        except Exception as e:
            print e
            print u'处理盘柜信息错误'

    # 采集风扇信息 show fan
    def __get_enclosure_fanmodule(self, ssh):
        datas = ssh.run_cmd('show fan')
        # with open('./ddn/fan') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx|')[1].split('Total')
        except Exception as e:
            print e
            print u'解析风扇信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'Idx' in rignt_data[0] or '---' in rignt_data[0]: continue

                enclosure_id = rignt_data[1]  # 盘柜ID
                RPM = rignt_data[4]  # 转速
                State = rignt_data[6]
                pos = rignt_data[3]
                res = {
                    "enclosure_id": enclosure_id,
                    "RPM": RPM,
                    "State": State,
                    "pos": pos,
                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理风扇信息错误'

    # 采集控制器信息 show controller
    def __get_enclosure_controller(self, ssh):
        datas = ssh.run_cmd('show controller')
        # with open('./ddn/controller') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx|')[1].split('Total')
        except Exception as e:
            print e
            print u'解析控制器信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'Name' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                Mastership = rignt_data[2]
                Locality = rignt_data[3]
                UpTime = rignt_data[4]
                EnclID = rignt_data[7]
                State = rignt_data[9]
                Release = rignt_data[11]
                Version = rignt_data[12]
                Type = rignt_data[13]

                res = {
                    "idx": idx,
                    "Mastership": Mastership,
                    "Locality": Locality,
                    "UpTime": UpTime,
                    "EnclID": EnclID,
                    "State": State,
                    "Version": Version,
                    "Type": Type,
                    "Release": Release,
                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理控制器信息错误'

    # 采集电池信息 show power_supply
    def __get_enclosure_battery(self, ssh):
        datas = ssh.run_cmd('show power_supply')
        # with open('./ddn/power_supply') as f:
        #     datas = f.read()

        try:
            datas = datas.split('Idx|')[1].split('Total')
        except Exception as e:
            print e
            print u'解析电池器信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'Idx' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                Enclosure_ID = rignt_data[2]
                State = rignt_data[4]
                pos = rignt_data[3]

                res = {
                    "idx": idx,
                    "Enclosure_ID": Enclosure_ID,
                    "State": State,
                    "pos": pos,
                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理电池信息错误'

    # 采集电压信息 show ups
    def __get_enclosure_psu(self, ssh):
        datas = ssh.run_cmd('show ups')
        # with open('./ddn/ups') as f:
        #     datas = f.read()

        try:
            datas = datas.split('Idx|')[1].split('Total')
        except Exception as e:
            print e
            print u'解析电压信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'Idx' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                Enclosure_ID = rignt_data[1]
                Charge = rignt_data[5]
                HoldUp = rignt_data[6] + ' ' + rignt_data[7]
                Health = rignt_data[10]
                SES_Status = rignt_data[-1]
                pos = rignt_data[3]

                res = {
                    # "idx": idx,
                    "Enclosure_ID": Enclosure_ID,
                    "SES_Status": SES_Status,
                    "Charge": Charge,
                    "HoldUp": HoldUp,
                    "Health": Health,
                    "pos": pos,
                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理电压信息错误'

    # 采集温度信息 show temperature
    def __get_enclosure_temperature(self, ssh):
        datas = ssh.run_cmd('show temperature')
        # with open('./ddn/temperature') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx|')[1].split('Total')
        except Exception as e:
            print e
            print u'解析温度信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'Idx' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                Enclosure_ID = rignt_data[1]
                pos = rignt_data[3]
                Temp = rignt_data[4]
                Location = rignt_data[10]
                SES_Status = rignt_data[11]

                res = {
                    "idx": idx,
                    "Enclosure_ID": Enclosure_ID,
                    "SES_Status": SES_Status,
                    "Location": Location,
                    "Temp": Temp + u' 摄氏度',
                    "pos": pos,
                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理温度信息错误'

    # 采集插号信息 show slot
    def __get_enclosure_solt(self, ssh):
        datas = ssh.run_cmd('show slot')
        # with open('./ddn/slot') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx|')[2].split('Total')
        except Exception as e:
            print e
            print u'解析插号信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if 'ID' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                Enclosure_ID = rignt_data[1]
                pos = rignt_data[3]
                PhysicalDiskIdx = rignt_data[4]
                PhysicalDiskID = rignt_data[5]
                State = rignt_data[6]
                SES_Status = rignt_data[12]

                res = {
                    "idx": idx,
                    "Enclosure_ID": Enclosure_ID,
                    "pos": pos,
                    "PhysicalDiskIdx": PhysicalDiskIdx,
                    "PhysicalDiskID": PhysicalDiskID,
                    "State": State,
                    "SES_Status": SES_Status,

                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理插号信息错误'

    # 采集pool信息 show pool
    def __get_pool(self, ssh):
        datas = ssh.run_cmd('show pool')
        # with open('./ddn/pool') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx')[1].split('Total')
        except Exception as e:
            print e
            print u'解析pool信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if '|Name' in rignt_data[0] or '---' in rignt_data[0]: continue

                idx = rignt_data[0]
                name = rignt_data[1]
                State = rignt_data[2]
                Chunk = rignt_data[3]
                Raid = rignt_data[4]
                TotalCap = rignt_data[5]
                FreeCap = rignt_data[6]
                MaxVD = rignt_data[7]
                Settings = rignt_data[8] + " " + rignt_data[9]
                Disk_T_O = rignt_data[11]
                Global_spare_pool = rignt_data[12]
                Block_Size = rignt_data[14]

                res = {
                    "idx": idx,
                    "pool_name": name,
                    "State": State,
                    "Chunk": Chunk,
                    "Raid": Raid,
                    "TotalCap": TotalCap + " GB",
                    "FreeCap": FreeCap + " GB",
                    "MaxVD": MaxVD + " GB",
                    "Settings": Settings,
                    "Disk_T_O": Disk_T_O,
                    "Global_spare_pool": Global_spare_pool,
                    "Block_Size": Block_Size,

                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理pool信息错误'

    # 采集物理盘信息，show PHYSICAL_DISK
    def __get_drive(self, ssh):
        datas = ssh.run_cmd('show PHYSICAL_DISK')
        # with open('./ddn/PHYSICAL_DISK') as f:
        #     datas = f.read()
        try:
            datas = datas.split('Idx')[2].split('| NUM')
        except Exception as e:
            print e
            print u'解析物理盘信息错误'

        try:
            info_list = []
            for data in datas[0].split('\n'):
                rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
                if len(data) <= 2: continue
                clean_data = data.split('\n')[0].split(' ')

                # 去掉空白
                for sprit in clean_data:
                    if sprit: rignt_data.append(sprit)

                # 去掉第一个名字开头
                if len(rignt_data) < 2 or '|State' in rignt_data[0]: continue

                Idx = rignt_data[12]
                Enclosure_id = rignt_data[0]
                Slot_id = rignt_data[2]
                ProductID = rignt_data[4]
                Type = rignt_data[5]
                Cap = rignt_data[6]
                RPM = rignt_data[7]
                SerialNumber = rignt_data[9]
                PoolID = rignt_data[10]
                HealthState = rignt_data[11]
                State = rignt_data[13]
                WWN = rignt_data[-2]
                BlockSize = rignt_data[-1]

                res = {
                    "Idx": Idx,
                    "Enclosure_id": Enclosure_id,
                    "Slot_id": Slot_id,
                    "ProductID": ProductID,
                    "Type": Type,
                    "Cap": Cap + " GB",
                    "RPM": RPM,
                    "SerialNumber": SerialNumber,
                    "PoolID": PoolID,
                    "HealthState": HealthState,
                    "State": State,
                    "WWN": WWN,
                    "BlockSize": BlockSize,

                }
                info_list.append(res)

            return info_list
        except Exception as e:
            print e
            print u'处理物理盘信息错误'

    # 下面是获取cmdb数据
    # 搜索盘柜实例
    def __search_enclosure(self):
        res_data = {}
        name_res = {}
        search_parms = {
            "fields": {
                "Idx": True,
                "name": True
            }
        }

        res_list = self.easyopsObj.instance_search('DISK_CABINET_DDN', search_parms)

        for res in res_list:
            instanceId = res.get('instanceId')
            name = res.get('name').split(":")[0]
            res_data.update({res.get('Idx'): instanceId})

            # 存储设备关系用到
            if not name_res.has_key(name):
                name_res[name] = []

            name_res[name].append(instanceId)

        return res_data, name_res

    # 搜索solt信息
    def __search_slots(self):
        res_data = {}
        search_parms = {
            "fields": {
                "idx": True
            }
        }

        res_list = self.easyopsObj.instance_search('SLOT_DDN', search_parms)

        for res in res_list:
            res_data.update({res.get('idx'): res.get('instanceId')})
        return res_data

    # 搜pool信息
    def __search_pools(self):
        res_data = {}
        name_res = {}
        search_parms = {
            "fields": {
                "idx": True,
                "name": True
            }
        }

        res_list = self.easyopsObj.instance_search('STORAGEPOOL_DDN', search_parms)

        for res in res_list:
            name = res.get('name').split(':')[0]
            instanceId = res.get('instanceId')
            res_data.update({res.get('idx'): instanceId})
            # 存储设备关系用到
            if not name_res.has_key(name):
                name_res[name] = []

            name_res[name].append(instanceId)

        return res_data, name_res

    # 搜索物理盘实例
    def __search_disk(self):
        res_data = {}
        search_parms = {
            "fields": {
                "name": True
            }
        }
        res_list = self.easyopsObj.instance_search('DISK_DDN', search_parms)
        for res in res_list:
            name = res.get('name').split(':')[0]
            if not res_data.has_key(name):
                res_data[name] = []
            res_data[name].append(res.get('instanceId'))

        return res_data

    # 下面是汇报数据
    # 采集盘柜，控制器，电源信息，温度等，并汇报
    def __post_enclosure(self, ssh, name):
        enclosure_data = []  # 盘柜信息
        enclosure_res = self.__get_enclosure(ssh)
        for res in enclosure_res:
            # 以存储设备名称 + ":" + id
            enclosure_name = str(name) + ':' + str(res.get('Idx'))
            res['name'] = enclosure_name
            enclosure_data.append(res)
        # -------------------------- 获取盘柜信息完

        enclosure_fanmodule_res = self.__get_enclosure_fanmodule(ssh)
        for res in enclosure_fanmodule_res:
            # 以存储设备名称 + ":" + id
            enclosure_fanmodule_name = str(name) + ':' + str(res.get('enclosure_id'))  # 风扇ID
            for enclosure in enclosure_data:
                if enclosure_fanmodule_name == enclosure.get('name'):
                    if not enclosure.has_key('fanmodule_res'):
                        enclosure['fanmodule_res'] = []
                    enclosure['fanmodule_res'].append(res)
        # -------------------------- 获取盘柜风扇信息完

        # 控制器信息
        controller_res = self.__get_enclosure_controller(ssh)
        for res in controller_res:
            # 以存储设备名称 + ":" + id
            enclosure_controller_name = str(name) + ':' + str(res.get('EnclID'))  # 盘柜ID
            for enclosure in enclosure_data:
                if enclosure_controller_name == enclosure.get('name'):
                    if not enclosure.has_key('controller'):
                        enclosure['controller'] = []
                    enclosure['controller'].append(res)

        # 电池信息
        enclosure_battery_res = self.__get_enclosure_battery(ssh)
        for res in enclosure_battery_res:
            # 以存储设备名称 + ":" + id
            enclosure_battery_name = str(name) + ':' + str(res.get('Enclosure_ID'))  # 盘柜ID
            for enclosure in enclosure_data:
                if enclosure_battery_name == enclosure.get('name'):
                    if not enclosure.has_key('battery_res'):
                        enclosure['battery_res'] = []
                    enclosure['battery_res'].append(res)
        # -------------------------- 获取盘柜电池信息完

        # 电源信息
        enclosure_psu_res = self.__get_enclosure_psu(ssh)
        # 以存储设备名称 + ":" + id
        for res in enclosure_psu_res:
            # 以存储设备名称 + ":" + id
            enclosure_psu_name = str(name) + ':' + str(res.get('Enclosure_ID'))  # 盘柜ID
            for enclosure in enclosure_data:
                if enclosure_psu_name == enclosure.get('name'):
                    if not enclosure.has_key('psu_res'):
                        enclosure['psu_res'] = []
                    enclosure['psu_res'].append(res)
        # -------------------------- 获取盘柜电源信息完

        # 温度
        enclosure_temperature_res = self.__get_enclosure_temperature(ssh)
        # 以存储设备名称 + ":" + id
        for res in enclosure_temperature_res:
            # 以存储设备名称 + ":" + id
            enclosure_temperature_name = str(name) + ':' + str(res.get('Enclosure_ID'))  # 盘柜ID
            for enclosure in enclosure_data:
                if enclosure_temperature_name == enclosure.get('name'):
                    if not enclosure.has_key('temperature_res'):
                        enclosure['temperature_res'] = []
                    enclosure['temperature_res'].append(res)
        # -------------------------- 获取盘柜温度信息完

        # 汇报磁盘柜信息
        enclosure_info = {
            "keys": ["name"],
            "datas": enclosure_data
        }

        if len(enclosure_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_CABINET_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, enclosure_info)
            print '磁盘柜信息采集完成:', res
        #
        return enclosure_data

    # 采集插号 信息 并汇报
    def __post_slots(self, ssh, name):
        slots_data = []
        # 插号
        enclosure_solt_res = self.__get_enclosure_solt(ssh)
        # 以存储设备名称 + ":" + id
        for res in enclosure_solt_res:
            # 以存储设备名称 + ":" + id
            enclosure_solt_name = str(name) + ':' + str(res.get('idx'))  # 盘柜ID
            res['name'] = enclosure_solt_name
            slots_data.append(res)
        # -------------------------- 获取盘柜插号信息完

        # 汇报pool 信息
        slot_info = {
            "keys": ["name"],
            "datas": slots_data
        }

        if len(slot_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('SLOT_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, slot_info)
            print '插号信息采集完成:', res

        return slots_data

    # 采集pool信息，并汇报
    def __post_pool(self, ssh, name):
        pool_data = []  # pool信息
        pool_res = self.__get_pool(ssh)
        for res in pool_res:
            # 以存储设备名称 + ":" + id
            pool_name = str(name) + ':' + str(res.get('idx'))
            res['name'] = pool_name
            pool_data.append(res)
        # -------------------------- 获取pool信息完

        # 汇报pool 信息
        pool_info = {
            "keys": ["name"],
            "datas": pool_data
        }

        if len(pool_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGEPOOL_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, pool_info)
            print 'pool 信息采集完成:', res

        return pool_data

    # 采集物理盘信息 并汇报
    def __post_drive(self, ssh, name):
        drive_data = []  # 物理盘信息
        drive_res = self.__get_drive(ssh)
        for res in drive_res:
            # 以存储设备名称 + ":" + id
            drive_name = str(name) + ':' + str(res.get('Idx'))
            res['name'] = drive_name
            drive_data.append(res)
        # -------------------------- 获取物理盘信息完

        # 汇报drive 物理盘信息
        drive_info = {
            "keys": ["name"],
            "datas": drive_data
        }

        if len(drive_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, drive_info)
            print 'drive 硬盘信息采集完成:', res

        return drive_data

    # 下面是设置关系
    # 设置盘柜和插条关系
    def __set_enclo_slot(self, slots_data, enclosure_res):
        set_inser_data = {
            "keys": ['name'],
            "datas": []
        }

        for slot in slots_data:
            Enclosure_ID = slot.get('Enclosure_ID')
            name = slot.get('name')
            if enclosure_res.has_key(Enclosure_ID):
                res = {
                    "name": name,
                    'DISK_CABINET_DDN': enclosure_res[Enclosure_ID]
                }
                set_inser_data['datas'].append(res)

        if len(set_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('SLOT_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, set_inser_data)
            print '设置插号和盘柜关系:', res

    # 设置物理盘和盘柜关系
    def __set_enclo_disk(self, drive_data, enclosure_res):
        set_inser_data = {
            "keys": ['name'],
            "datas": []
        }

        for slot in drive_data:
            Enclosure_ID = slot.get('Enclosure_id')
            name = slot.get('name')

            if enclosure_res.has_key(Enclosure_ID):
                res = {
                    "name": name,
                    'DISK_CABINET_DDN': enclosure_res[Enclosure_ID]
                }
                set_inser_data['datas'].append(res)

        if len(set_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, set_inser_data)
            print '设置物理盘和盘柜关系:', res

    # 设置物理盘和slot关系
    def __set_disk_slot(self, drive_data, slots_res):
        set_inser_data = {
            "keys": ['name'],
            "datas": []
        }

        for slot in drive_data:
            Slot_id = slot.get('Slot_id')
            name = slot.get('name')

            if slots_res.has_key(Slot_id):
                res = {
                    "name": name,
                    'SLOT_DDN': slots_res[Slot_id]
                }
                set_inser_data['datas'].append(res)

        if len(set_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, set_inser_data)
            print '设置物理盘和插号关系:', res

    # 设置物理盘和pool关系
    def __set_disk_pool(self, drive_data, pools_res):
        set_inser_data = {
            "keys": ['name'],
            "datas": []
        }

        for drive in drive_data:
            pool_id = drive.get('PoolID')
            name = drive.get('name')

            if pools_res.has_key(pool_id):
                res = {
                    "name": name,
                    'STORAGEPOOL_DDN': pools_res[pool_id]
                }
                set_inser_data['datas'].append(res)

        if len(set_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_DDN')
            res = self.easyopsObj.http_post('many_post', info_url, set_inser_data)
            print '设置物理盘和pool关系:', res

    # 设置存储设备和物理盘，pool，盘柜信息
    def __set_device(self, disk_res, pools_name_res, enclosure_name_res):

        # 物理盘和存储设备
        disk_inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name, inses in disk_res.items():
            res = {
                "name": name,
                "DISK_DDN": inses
            }
            disk_inser_data['datas'].append(res)

        if len(disk_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, disk_inser_data)
            print '设置物理盘和存储设备关系:', res

        # pool和存储设备
        pool_data = {
            "keys": ['name'],
            "datas": []
        }

        for name, inses in pools_name_res.items():
            res = {
                "name": name,
                "STORAGEPOOL_DDN": inses
            }
            pool_data['datas'].append(res)

        if len(pool_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, pool_data)
            print '设置pool和存储设备关系:', res

        # 盘柜和存储设备
        enclosure_data = {
            "keys": ['name'],
            "datas": []
        }

        for name, inses in enclosure_name_res.items():
            res = {
                "name": name,
                "DISK_CABINET_DDN": inses
            }
            enclosure_data['datas'].append(res)

        if len(enclosure_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, enclosure_data)
            print '设置盘柜和存储设备关系:', res

    def dealdata(self, content):
        for data in content:
            name = data.get("name")
            ip = data.get('ip')
            username = data.get('username')
            password = data.get('password')
            # 初始化ssh
            ssh = ParamikoConn(user=username, passwd=password, ip=ip)

            # 盘柜，电池， 电源信息，并汇报，enclosure_data
            enclosure_data = self.__post_enclosure(ssh, name)

            # 获取插号信息
            slots_data = self.__post_slots(ssh, name)

            # 采集pool信息 并汇报， pool_data
            pool_data = self.__post_pool(ssh, name)

            # 采集物理盘信息，并汇报 drive_data
            drive_data = self.__post_drive(ssh, name)

            ssh.close()

            # 盘柜和插号的关系
            # 1。1 先获取盘柜ID
            # 1.2 先获取所有盘柜信息，以盘柜ID： 实例ID组合
            # 获取盘柜实例ID
            enclosure_res, enclosure_name_res = self.__search_enclosure()
            # 获取插号实例
            slots_res = self.__search_slots()
            # 获取POOL实例
            pools_res, pools_name_res = self.__search_pools()
            # 获取物理盘实例
            disk_res = self.__search_disk()

            # 设置盘柜和插号关系
            self.__set_enclo_slot(slots_data, enclosure_res)
            # 设置物理盘和盘柜信息，物理盘和插号，物理盘和池的关系
            # 物理盘和盘柜关系
            self.__set_enclo_disk(drive_data, enclosure_res)
            # 设置物理盘和插号关系
            self.__set_disk_slot(drive_data, slots_res)
            # 设置物理盘和池的关系
            self.__set_disk_pool(drive_data, pools_res)

            # 设置存储设备和pool，物理盘，盘柜信息
            self.__set_device(disk_res, pools_name_res, enclosure_name_res)

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
