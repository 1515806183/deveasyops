# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re, paramiko, warnings
import threading
from Queue import Queue
from paramiko import SSHClient
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
ConfigSWITCHMODEL = 'STORAGE_DEVICE'

# 搜索实列列表条件
ConfigParams = {
    "query": {
        "collection_type": {"$eq": "v7000"},
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

    # 基本信息
    def __info_data(self, ssh):
        try:
            info_data = {}
            # 先采集基本信息，uuid, 制造商  lssystem
            res = ssh.run_cmd('lssystem')
            # with open('./v7000/lssystem') as f:
            #     res = f.read()
            datas = ''.join(res)

            # 存储别名
            try:
                id_alias = re.search(r'id_alias\s+(.*)', datas).group(1)
            except Exception as e:
                id_alias = ""
                print e
            info_data["id_alias"] = id_alias.split('\r')[0]

            # 产品名称
            try:
                product_name = re.search(r'product_name\s+(.*)', datas).group(1)
            except Exception as e:
                product_name = ''
                print e
            info_data['product_name'] = product_name.split('\r')[0]

            # 总mdisk容量
            try:
                total_mdisk_capacity = re.search(r'total_mdisk_capacity\s+(.*)', datas).group(1)
            except Exception as e:
                total_mdisk_capacity = ''
                print e
            info_data['total_mdisk_capacity'] = total_mdisk_capacity.split('\r')[0]

            # 使用的mdisk空间
            try:
                space_in_mdisk_grps = re.search(r'space_in_mdisk_grps\s+(.*)', datas).group(1)
            except Exception as e:
                space_in_mdisk_grps = ''
                print e
            info_data['space_in_mdisk_grps'] = space_in_mdisk_grps.split('\r')[0]

            # 分配的vdisk空间
            try:
                space_allocated_to_vdisks = re.search(r'space_allocated_to_vdisks\s+(.*)', datas).group(1)
            except Exception as e:
                space_allocated_to_vdisks = ''
                print e
            info_data['space_allocated_to_vdisks'] = space_allocated_to_vdisks.split('\r')[0]

            # 总可用空间
            try:
                total_free_space = re.search(r'total_free_space\s+(.*)', datas).group(1)
            except Exception as e:
                total_free_space = ''
                print e
            info_data['total_free_space'] = total_free_space.split('\r')[0]

            # 磁盘总空间
            try:
                total_vdiskcopy_capacity = re.search(r'total_vdiskcopy_capacity\s+(.*)', datas).group(1)
            except Exception as e:
                total_vdiskcopy_capacity = ''
                print e
            info_data['total_vdiskcopy_capacity'] = total_vdiskcopy_capacity.split('\r')[0]

            # 已用总容量
            try:
                total_used_capacity = re.search(r'total_used_capacity\s+(.*)', datas).group(1)
            except Exception as e:
                total_used_capacity = ''
                print e
            info_data['total_used_capacity'] = total_used_capacity.split('\r')[0]

            # 磁盘总容量
            try:
                total_vdisk_capacity = re.search(r'total_vdisk_capacity\s+(.*)', datas).group(1)
            except Exception as e:
                total_vdisk_capacity = ''
                print e
            info_data['total_vdisk_capacity'] = total_vdisk_capacity.split('\r')[0]

            # 分配的总扩展容量
            try:
                total_allocated_extent_capacity = re.search(r'total_allocated_extent_capacity\s+(.*)', datas).group(1)
            except Exception as e:
                total_allocated_extent_capacity = ''
                print e
            info_data['total_allocated_extent_capacity'] = total_allocated_extent_capacity.split('\r')[0]

            # 缓冲区大小
            try:
                rc_buffer_size = re.search(r'rc_buffer_size\s+(.*)', datas).group(1)

            except Exception as e:
                rc_buffer_size = ''
                print e
            info_data['rc_buffer_size'] = rc_buffer_size.split('\r')[0]

            # 物理容量
            try:
                physical_capacity = re.search(r'physical_capacity\s+(.*)', datas).group(1)

            except Exception as e:
                physical_capacity = ''
                print e
            info_data['physical_capacity'] = physical_capacity.split('\r')[0]

            # 物理可用容量
            try:
                physical_free_capacity = re.search(r'physical_free_capacity\s+(.*)', datas).group(1)

            except Exception as e:
                physical_free_capacity = ''
                print e
            info_data['physical_free_capacity'] = physical_free_capacity.split('\r')[0]

            return info_data

        except Exception as e:
            print e

    # 获取LUN信息
    def __get_lun_info(self, ssh):
        datas = ssh.run_cmd('lsvdisk')
        # with open('./v7000/lsvdisk') as f:
        #     datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split('\n\r')[0].split(' ')
            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'id':
                continue
            id = rignt_data[0]
            name = rignt_data[1]
            status = rignt_data[4]
            mdisk_grp_name = rignt_data[6]
            capacity = rignt_data[7]
            type = rignt_data[8]
            vdisk_UID = rignt_data[9]
            volume_name = rignt_data[-2]

            res = {
                "id": id,
                "name": name,
                "status": status,
                "mdisk_grp_name": mdisk_grp_name,
                "capacity": capacity,
                "type": type,
                "volume_name": volume_name,
                "vdisk_UID": vdisk_UID,
            }
            info_list.append(res)

        return info_list

    # 获取mdisk信息
    def __get_mdisk(self, ssh):
        datas = ssh.run_cmd('lsarray')
        # with open('./v7000/lsarray') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'mdisk_id':
                continue

            mdisk_id = rignt_data[0]
            mdisk_name = rignt_data[1]
            status = rignt_data[2]
            mdisk_grp_name = rignt_data[4]
            capacity = rignt_data[5]
            raid_status = rignt_data[6]
            raid_level = rignt_data[7]
            strip_size = rignt_data[9]

            res = {
                "mdisk_id": mdisk_id,
                "name": mdisk_name,
                "status": status,
                "mdisk_grp_name": mdisk_grp_name,
                "capacity": capacity,
                "raid_status": raid_status,
                "raid_level": raid_level,
                "strip_size": strip_size,
            }
            info_list.append(res)
        return info_list

    # 获取pool信息
    def __get_pool(self, ssh):
        datas = ssh.run_cmd('lsmdiskgrp')
        # with open('./v7000/lsmdiskgrp') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'id':
                continue

            id = rignt_data[0]
            name = rignt_data[1]
            status = rignt_data[2]
            mdisk_count = rignt_data[3]
            vdisk_count = rignt_data[4]
            capacity = rignt_data[5]
            extent_size = rignt_data[6]
            free_capacity = rignt_data[7]
            virtual_capacity = rignt_data[8]
            used_capacity = rignt_data[9]
            real_capacity = rignt_data[10]
            overallocation = rignt_data[11]

            res = {
                "id": id,
                "name": name,
                "status": status,
                "mdisk_count": mdisk_count,
                "vdisk_count": vdisk_count,
                "capacity": capacity,
                "extent_size": extent_size,
                "free_capacity": free_capacity,
                "virtual_capacity": virtual_capacity,
                "used_capacity": used_capacity,
                "real_capacity": real_capacity,
                "overallocation": overallocation,
            }

            info_list.append(res)

        return info_list

    # 获取物理盘信息
    def __get_drive(self, ssh):
        datas = ssh.run_cmd('lsdrive')
        # with open('./v7000/lsdrive') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'id':
                continue

            try:
                id = rignt_data[0]
            except:
                id = ''

            try:
                status = rignt_data[1]
            except:
                status = ''

            try:
                use = rignt_data[2]
            except:
                use = ''

            try:
                tech_type = rignt_data[3]
            except:
                tech_type = ''

            try:
                capacity = rignt_data[4]
            except:
                capacity = ''

            if use in ['spare', 'candidate']:
                mdisk_id = ''
                mdisk_name = ''
                member_id = ''

                try:
                    enclosure_id = rignt_data[5]
                except:
                    enclosure_id = ''

                try:
                    slot_id = rignt_data[6]
                except:
                    slot_id = ''

            else:

                try:
                    mdisk_id = rignt_data[5]
                except:
                    mdisk_id = ''

                try:
                    mdisk_name = rignt_data[6]
                except:
                    mdisk_name = ''

                try:
                    member_id = rignt_data[7]
                except:
                    member_id = ''

                try:
                    enclosure_id = rignt_data[8]
                except:
                    enclosure_id = ''

                try:
                    slot_id = rignt_data[9]
                except:
                    slot_id = ''

            res = {
                "id": id,
                "status": status,
                "use": use,
                "tech_type": tech_type,
                "mdisk_id": mdisk_id,
                "mdisk_name": mdisk_name,
                "member_id": member_id,
                "enclosure_id": enclosure_id,
                "slot_id": slot_id,
                "capacity": capacity,
            }
            info_list.append(res)

        return info_list

    # 获取盘柜信息
    def __get_enclosure(self, ssh):
        datas = ssh.run_cmd('lsenclosure')
        # with open('./v7000/lsenclosure') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'id':
                continue

            id = rignt_data[0]
            status = rignt_data[1]
            type = rignt_data[2]
            product_MTM = rignt_data[6]
            serial_number = rignt_data[7]
            total_canisters = rignt_data[8]
            online_canisters = rignt_data[9]
            total_PSUs = rignt_data[10]
            online_PSUs = rignt_data[11]
            drive_slots = rignt_data[12]
            total_fan_modules = rignt_data[13]
            online_fan_modules = rignt_data[14]
            res = {
                "id": id,
                "status": status,
                "type": type,
                "product_MTM": product_MTM,
                "serial_number": serial_number,
                "total_canisters": total_canisters,
                "online_canisters": online_canisters,
                "total_PSUs": total_PSUs,
                "online_PSUs": online_PSUs,
                "drive_slots": drive_slots,
                "total_fan_modules": total_fan_modules,
                "online_fan_modules": online_fan_modules,
            }
            info_list.append(res)

        return info_list

    # 获取盘柜电池信息
    def __get_enclosure_battery(self, ssh):
        datas = ssh.run_cmd('lsenclosurebattery')
        # with open('./v7000/lsenclosurebattery') as f:
        #   datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'enclosure_id':
                continue

            enclosure_id = rignt_data[0]  # 盘柜ID
            battery_id = rignt_data[1]  # 电池id
            status = rignt_data[2]  # 电池id
            charging_status = rignt_data[3]
            recondition_needed = rignt_data[4]  # 是否需要修复

            res = {
                "enclosure_id": enclosure_id,
                "battery_id": battery_id,
                "status": status,
                "charging_status": charging_status,
                "recondition_needed": recondition_needed,
            }

            info_list.append(res)

        return info_list

    # 获取盘柜风扇信息
    def __get_enclosure_fanmodule(self, ssh):
        datas = ssh.run_cmd('lsenclosurefanmodule')
        # with open('./v7000/lsenclosurefanmodule') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'enclosure_id':
                continue

            enclosure_id = rignt_data[0]  # 盘柜ID
            fan_module_id = rignt_data[1]  # 电池id
            status = rignt_data[2]  # 状态

            res = {
                "enclosure_id": enclosure_id,
                "fan_module_id": fan_module_id,
                "status": status,
            }

            info_list.append(res)

        return info_list

    # 获取盘柜电源信息
    def __get_enclosure_psu(self, ssh):
        datas = ssh.run_cmd('lsenclosurepsu')
        # with open('./v7000/lsenclosurepsu') as f:
        #    datas = f.readlines()

        info_list = []
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'enclosure_id':
                continue

            enclosure_id = rignt_data[0]  # 盘柜ID
            PSU_id = rignt_data[1]  # 电池id
            status = rignt_data[2]  # 状态
            input_power = rignt_data[3]

            res = {
                "enclosure_id": enclosure_id,
                "PSU_id": PSU_id,
                "status": status,
                "input_power": input_power
            }

            info_list.append(res)

        return info_list

    # 获取lun和主机关系信息
    def __get_lun_host(self, ssh, cmd):
        datas = ssh.run_cmd(cmd)
        # with open('./v7000/lsvdiskhostmap') as f:
        #    datas = f.readlines()

        # 可能没有主机存在
        info_list = {}
        for data in datas:
            rignt_data = []  # 这个保存清理完空格的数据，最下面要重置
            clean_data = data.split('\n\r')[0].split(' ')

            # 去掉空白
            for sprit in clean_data:
                if sprit: rignt_data.append(sprit)
            # 去掉第一个名字开头
            if rignt_data[0] == 'id':
                continue

            host_name = rignt_data[4]
            lun_uuid = rignt_data[5]
            if not info_list.has_key(lun_uuid):
                info_list[lun_uuid] = []
            info_list[lun_uuid].append(host_name)
        return info_list

    # 采集基本信息并汇报
    def __post_infos(self, ssh, name):
        basic_data = []  # 基本信息
        info_data = self.__info_data(ssh)  # 处理基本信息
        basic_data.append({"name": name, "info_data": [info_data]})
        # -------------------------- 基本信息完

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

    # 采集lun，并汇报
    def __post_lun(self, ssh, name):
        lun_data = []  # lun

        lun_res = self.__get_lun_info(ssh)
        for res in lun_res:
            # 以存储设备名称 + ":" + lun_name
            lun_name = str(name) + ':' + str(res.get('vdisk_UID'))
            res['name'] = lun_name
            lun_data.append(res)
        # -------------------------- LUN信息完

        # 汇报lun信息
        lun_info = {
            "keys": ["name"],
            "datas": lun_data
        }

        if len(lun_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGELUN')
            res = self.easyopsObj.http_post('many_post', info_url, lun_info)
            print 'lun信息采集完成:', res

        return lun_data

    # 采集 mkdis 信息 并汇报
    def __post_mkdis(self, ssh, name):
        mkdis_data = []  # mkdis 信息
        mdiks_res = self.__get_mdisk(ssh)
        for res in mdiks_res:
            # 以存储设备名称 + ":" + mkdis name
            mdisk_name = str(name) + ':' + str(res.get('name'))
            res['name'] = mdisk_name
            mkdis_data.append(res)
        # -------------------------- mdiks完

        # 汇报mdisk信息
        mdisk_info = {
            "keys": ["name"],
            "datas": mkdis_data
        }

        if len(mdisk_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE')
            res = self.easyopsObj.http_post('many_post', info_url, mdisk_info)
            print 'mdisk信息采集完成:', res

        return mkdis_data

    # 采集 pool_data信息 并汇报
    def __post_pool(self, ssh, name):
        pool_data = []  # pool 信息
        pool_res = self.__get_pool(ssh)
        for res in pool_res:
            # 以存储设备名称 + ":" + mkdis name
            pool_name = str(name) + ':' + str(res.get('name'))
            res['name'] = pool_name
            pool_data.append(res)
        # -------------------------- pool完

        # 汇报pool信息
        pool_info = {
            "keys": ["name"],
            "datas": pool_data
        }

        if len(pool_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGEPOOL')
            res = self.easyopsObj.http_post('many_post', info_url, pool_info)
            print 'pool信息采集完成:', res

        return pool_data

    # 采集物理盘信息 并汇报
    def __post_drive(self, ssh, name):
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
            info_url = "/object/{0}/instance/_import".format('DISK')
            res = self.easyopsObj.http_post('many_post', info_url, drive_info)
            print 'drive 硬盘信息采集完成:', res

        return drive_data

    # 采集盘柜，电池， 电源信息 并汇报
    def __post_enclosure(self, ssh, name):
        enclosure_data = []  # 盘柜信息
        enclosure_res = self.__get_enclosure(ssh)
        for res in enclosure_res:
            # 以存储设备名称 + ":" + id
            enclosure_name = str(name) + ':' + str(res.get('id'))
            res['name'] = enclosure_name
            enclosure_data.append(res)
        # -------------------------- 获取盘柜信息完

        enclosure_battery_res = self.__get_enclosure_battery(ssh)
        for res in enclosure_battery_res:
            # 以存储设备名称 + ":" + id
            enclosure_battery_name = str(name) + ':' + str(res.get('enclosure_id'))  #
            for enclosure in enclosure_data:
                if enclosure_battery_name == enclosure.get('name'):
                    if not enclosure.has_key('battery_res'):
                        enclosure['battery_res'] = []
                    enclosure['battery_res'].append(res)
                    break
        # -------------------------- 获取盘柜电池信息完

        enclosure_fanmodule_res = self.__get_enclosure_fanmodule(ssh)
        for res in enclosure_fanmodule_res:
            # 以存储设备名称 + ":" + id
            enclosure_fanmodule_name = str(name) + ':' + str(res.get('enclosure_id'))  #
            for enclosure in enclosure_data:
                if enclosure_fanmodule_name == enclosure.get('name'):
                    if not enclosure.has_key('fanmodule_res'):
                        enclosure['fanmodule_res'] = []
                    enclosure['fanmodule_res'].append(res)
                    break
        # -------------------------- 获取盘柜风扇信息完

        enclosure_psu_res = self.__get_enclosure_psu(ssh)
        # 以存储设备名称 + ":" + id
        for res in enclosure_psu_res:
            # 以存储设备名称 + ":" + id
            enclosure_psu_name = str(name) + ':' + str(res.get('enclosure_id'))  #
            for enclosure in enclosure_data:
                if enclosure_psu_name == enclosure.get('name'):
                    if not enclosure.has_key('psu_res'):
                        enclosure['psu_res'] = []
                    enclosure['psu_res'].append(res)
                    break
        # -------------------------- 获取盘柜电源信息完

        # 汇报磁盘柜信息
        enclosure_info = {
            "keys": ["name"],
            "datas": enclosure_data
        }

        if len(enclosure_info["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_CABINET')
            res = self.easyopsObj.http_post('many_post', info_url, enclosure_info)
            print '磁盘柜信息采集完成:', res

        return enclosure_data

    # search 所有存储列表
    def __search_staorge(self):
        search_storage = {
            "fields": {
                "name": True,
                "mdisk_id": True,
                "mdisk_grp_name": True
            }
        }
        storge_list = self.easyopsObj.instance_search('STORAGE', search_storage)
        storge_disk_data_list = {}  # 硬盘和组用到
        pool_data_list = {}  # 硬盘组和pool
        name_device = {}  # 存储设备设备关系用到
        if storge_list:
            for storge in storge_list:
                name = storge.get('name')
                instanceId = storge.get('instanceId')
                mdisk_id = storge.get('mdisk_id')
                mdisk_grp_name = storge.get('mdisk_grp_name')
                # 提取name,name + : + mdisk_id, mdisk_grp_name
                instanceId_name = str(name).split(":")[0]
                mdisk_id_name = instanceId_name + ":" + mdisk_id
                mdisk_grp_name = instanceId_name + ":" + mdisk_grp_name
                storge_disk_data_list.update({name: mdisk_id_name})
                if not pool_data_list.has_key(mdisk_grp_name):
                    pool_data_list[mdisk_grp_name] = []
                pool_data_list[mdisk_grp_name].append(instanceId)

                # 存储设备和组
                dervice_name = str(name).split(":")[0]
                if not name_device.has_key(dervice_name):
                    name_device[dervice_name] = []
                name_device[dervice_name].append(instanceId)

        return storge_disk_data_list, pool_data_list, name_device

    # search 所有disk列表
    def __search_disk(self):
        search_disk = {
            "fields": {
                "name": True,
                "mdisk_id": True,
                "enclosure_id": True,  # 所在磁盘柜
                "slot_id": True,  # 盘柜插号
            }
        }
        disk_list = self.easyopsObj.instance_search('DISK', search_disk)
        disk_datas = {}  # 硬盘和组
        enclosure_datas = {}
        if disk_list:
            for disk in disk_list:
                enclosure_id = disk.get('enclosure_id')
                mdisk_id = disk.get('mdisk_id')
                instanceId = disk.get('instanceId')
                if mdisk_id:
                    name = str(disk.get('name')).split(":")[0] + ":" + mdisk_id
                    disk_mdisk_id_name = name
                    if not disk_datas.has_key(disk_mdisk_id_name):
                        disk_datas[disk_mdisk_id_name] = []
                    disk_datas[disk_mdisk_id_name].append(instanceId)

                # 盘柜号，有些是 inactive
                if 1 <= len(enclosure_id) <= 2:
                    name = str(disk.get('name')).split(":")[0]
                    # 名称 + ":" + enclosure_id
                    enclosure_id_name = name + ":" + enclosure_id
                    if not enclosure_datas.has_key(enclosure_id_name):
                        enclosure_datas[enclosure_id_name] = []
                    enclosure_datas[enclosure_id_name].append(instanceId)

        return disk_datas, enclosure_datas

    # search 所有盘柜列表
    def __search_cabinet(self):
        search_cabinet = {
            "fields": {
                "name": True,
            }
        }
        cabine_list = self.easyopsObj.instance_search('DISK_CABINET', search_cabinet)
        cabine_data = {}
        if cabine_list:
            for cabine in cabine_list:
                instanceId = cabine.get('instanceId')
                name = str(cabine.get('name')).split(":")[0]
                if not cabine_data.has_key(name):
                    cabine_data[name] = []
                cabine_data[name].append(instanceId)

        return cabine_data

    # search 所有pool列表
    def __search_pool(self):
        search_pool = {
            "fields": {
                "name": True,
            }
        }
        pool_list = self.easyopsObj.instance_search('STORAGEPOOL', search_pool)
        pool_datas = {}
        if pool_list:
            for pool in pool_list:
                instanceId = pool.get('instanceId')
                name = str(pool.get('name')).split(":")[0]
                if not pool_datas.has_key(name):
                    pool_datas[name] = []
                pool_datas[name].append(instanceId)

        return pool_datas

    # search 所有hosts列表
    def __search_hosts(self):
        search_host = {
            "fields": {
                "hostname": True,
            }
        }
        host_list = self.easyopsObj.instance_search('HOST', search_host)
        host_datas = {}
        if host_list:
            for host in host_list:
                instanceId = host.get('instanceId')
                hostname = host.get('hostname')
                if not host_datas.has_key(hostname):
                    host_datas[hostname] = []
                host_datas[hostname].append(instanceId)

        return host_datas

    # 设置关系
    def __set_relationship(self, storge_disk_data_list, disk_datas, pool_data_list, enclosure_datas, name_device,
                           cabine_data, pool_datas):
        # 1.3 设置存储和磁盘的关系

        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for storge_name, storge_mdisk_name in storge_disk_data_list.items():
            for disk_mdisk_name in disk_datas:
                if storge_mdisk_name == disk_mdisk_name:
                    data = {
                        "name": storge_name,
                        "DISK": disk_datas[disk_mdisk_name]
                    }
                    inser_data['datas'].append(data)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置存储和硬盘关系:', res

        # 1.4 设置存储池概关系
        pool_inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for data in pool_data_list:
            res = {
                "name": data,
                "STORAGE": pool_data_list[data]
            }
            pool_inser_data['datas'].append(res)

        if len(pool_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGEPOOL')
            res = self.easyopsObj.http_post('many_post', info_url, pool_inser_data)
            print '设置和pool关系:', res

        # 1.5 Lun和pool的关系
        # 1.5.1获取lun 的信息
        search_lun = {
            "fields": {
                "name": True,
                "mdisk_grp_name": True
            }
        }
        lun_list = self.easyopsObj.instance_search('STORAGELUN', search_lun)
        lun_insta = {}
        device_lun_data = {}
        if lun_list:
            for lun in lun_list:
                name = lun.get('name')
                instanceId = lun.get('instanceId')
                mdisk_grp_name = lun.get('mdisk_grp_name', '')
                if mdisk_grp_name:
                    mdisk_grp_name = str(name).split(':')[0] + ":" + mdisk_grp_name
                    if not lun_insta.has_key(mdisk_grp_name):
                        lun_insta[mdisk_grp_name] = []
                    lun_insta[mdisk_grp_name].append(instanceId)

                # lun和存储设备关系
                device_lun_name = str(name).split(':')[0]
                if not device_lun_data.has_key(device_lun_name):
                    device_lun_data[device_lun_name] = []
                device_lun_data[device_lun_name].append(instanceId)

        # 1.5.2 lun和pool设置关系
        pool_inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for lun in lun_insta:
            res = {
                "name": lun,
                "STORAGELUN": lun_insta[lun]
            }
            pool_inser_data['datas'].append(res)

        if len(pool_inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGEPOOL')
            res = self.easyopsObj.http_post('many_post', info_url, pool_inser_data)
            print '设置Lun和pool关系:', res

        # 1.6 设置硬盘和盘柜关系
        disk_cabinet_data = {
            "keys": ['name'],
            "datas": []
        }
        for cabinet in enclosure_datas:
            res = {
                "name": cabinet,
                "DISK": enclosure_datas[cabinet]
            }
            disk_cabinet_data['datas'].append(res)

        if len(disk_cabinet_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('DISK_CABINET')
            res = self.easyopsObj.http_post('many_post', info_url, disk_cabinet_data)
            print '设置硬盘和盘柜关系:', res

        # 1.7 设置存储设备和硬盘组关系
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for name in name_device:
            res = {
                "name": name,
                "STORAGE": name_device[name]
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置组和存储设备关系:', res

        # 1.8 s合作lun和存储设备关系
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for lun in device_lun_data:
            res = {
                "name": lun,
                "STORAGELUN": device_lun_data[lun]
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置LUN和存储设备关系:', res

        # 1.9 设置盘柜和资源池关系
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for cabine in cabine_data:
            res = {
                "name": cabine,
                "DISK_CABINET": cabine_data[cabine]
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置盘柜和存储设备关系:', res

        # 2 设置pool和资源设备关系
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        for pool in pool_datas:
            res = {
                "name": pool,
                "STORAGEPOOL": pool_datas[pool]
            }
            inser_data['datas'].append(res)

        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGE_DEVICE')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置盘柜和存储设备关系:', res

    def __set_lun_to_host(self, ssh, lun_data, host_datas):
        # 3. 获取lun和主机的关系
        inser_data = {
            "keys": ['name'],
            "datas": []
        }
        cmds = ''
        lun_uuid_name = []
        for lun in lun_data:
            lun_id = lun.get('id')
            name = lun.get('name')
            cmds += "lsvdiskhostmap " + str(lun_id) + " && "
            lun_uuid_name.append(name)

        # 根据LUN id 获取对应的主机关系信息
        lun_info_data = self.__get_lun_host(ssh, cmds[:-4])
        # lun_info_data 里面是lun_name 和[主机名], host_datas 是主机名 + 【实例ID】

        lun_name_hostinstart = {}  # lun uuid  + 主机实例ID
        for lun_name, host_list in lun_info_data.items():
            # print lun_name, host_list
            for host in host_list:
                if host_datas.has_key(host):
                    hostinstar = host_datas[host]
                    if not lun_name_hostinstart.has_key(lun_name):
                        lun_name_hostinstart[lun_name] = []
                    lun_name_hostinstart[lun_name] += hostinstar

        # 循环判断哪些主机属于那条lun name
        for lun_uuid, host_instart_list in lun_name_hostinstart.items():
            for lun_name in lun_uuid_name:
                if lun_uuid in lun_name:
                    res = {
                        "name": lun_name,
                        "HOST": host_instart_list
                    }
                    inser_data['datas'].append(res)
                    break
        if len(inser_data["datas"]):
            info_url = "/object/{0}/instance/_import".format('STORAGELUN')
            res = self.easyopsObj.http_post('many_post', info_url, inser_data)
            print '设置Lun和主机关系:', res

    def dealdata(self, content):
        for data in content:
            name = data.get("name")
            ip = data.get('ip')
            username = data.get('username')
            password = data.get('password')
            # 初始化ssh
            ssh = ParamikoConn(user=username, passwd=password, ip=ip)

            # 采集基本信息，并汇报 basic_data
            self.__post_infos(ssh, name)

            # 采集lun信息，并汇报， # lun 信息lun_data
            lun_data = self.__post_lun(ssh, name)

            # 采集mkdis信息，并汇报，mkdis_data
            self.__post_mkdis(ssh, name)

            # 采集pool信息，并汇报， pool_data
            self.__post_pool(ssh, name)

            # 采集物理盘信息，并汇报，drive_data
            self.__post_drive(ssh, name)

            # 盘柜，电池， 电源信息，并汇报，enclosure_data
            self.__post_enclosure(ssh, name)

            # 汇报数据完成---- 设置关系做铺垫--------------------------------------------
            # 1. 先获取所有的存储列表：STORAGE
            storge_disk_data_list, pool_data_list, name_device = self.__search_staorge()

            # 1.2 获取硬盘的信息
            disk_datas, enclosure_datas = self.__search_disk()

            # 1.3 盘柜信息CABINET
            cabine_data = self.__search_cabinet()

            # 1.4 pool信息
            pool_datas = self.__search_pool()

            # 1.5 获取主机信息
            host_datas = self.__search_hosts()

            #  上面是获取信息 为下面做关系铺垫 ------------------------------------------
            # 开始设置关系
            self.__set_relationship(storge_disk_data_list, disk_datas, pool_data_list, enclosure_datas, name_device,
                                    cabine_data, pool_datas)

            # 设置lun和主机关系
            self.__set_lun_to_host(ssh, lun_data, host_datas)

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
