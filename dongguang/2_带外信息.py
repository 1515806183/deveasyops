# -*- coding:utf-8 -*-
import requests
import threading
import json
import sys
import re
import os

reload(sys)
sys.setdefaultencoding('utf-8')


# dell 刀片机信息采集脚本


class EasyOps(object):
    def __init__(self, easy_host=None,
                 easy_domain='cmdb_resource.easyops-only.com',
                 easy_org=None,
                 easy_user='easyops'):
        self.easy_host = easy_host
        self.easy_domain = easy_domain
        self.easy_org = easy_org
        self.easy_user = easy_user
        self.easy_headers = {'host': self.easy_domain, 'org': self.easy_org, 'user': self.easy_user,
                             'content-Type': 'application/json'}
        self.ErrorType = {130313: u'数据重复', 130600: u'权限错误', 130300: u'数据库错误', 133117: u'外键关联错误', 130500: u'未知参数错误'}
        self.cmdb_result = dict()

    def http_post(self, restful_api, params):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=self.easy_host, restful_api=restful_api)
        try:
            response = requests.post(url, headers=self.easy_headers, data=json.dumps(params))
            response_json = response.json()
            if response.status_code == 200:
                if response_json['code'] == 0:
                    return response_json['data']  # success
            return {}
        except Exception as e:
            raise e

    def http_request(self, restful_api, method="GET", headers={}, **kwargs):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=self.easy_host, restful_api=restful_api)
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            response_json = response.json()
            if response.status_code == 200:
                if response_json['code'] == 0:
                    return 0, response_json['data']
            return 1, response.text
        except Exception as e:
            raise e

    def instance_search(self, object_id, params={}):
        page_size = 1000
        params['page_size'] = page_size
        params['page'] = 1
        search_result = self.http_post(
            restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
            params=params)
        total_instance_nums = int(search_result.get('total', 0))
        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 1):
                params['page'] = cur_page
                tmp_result = self.http_post(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                    params=params)
                search_result['list'] += tmp_result['list']
        return search_result

    def search_out_band_isinstances(self):
        return self.instance_search("OUT_OF_BAND_MANAGEMENT")

    def put_cmdb_instance(self, obj, instanceid, data):
        '''
            @docs: http://doc.easyops.local/cmdb_resource/3.36.x/3.36.24/API.md#-%E5%AE%9E%E4%BE%8B%E4%BF%AE%E6%94%B9
            :param obj: 对象ID
            :param instanceid: 实例ID
            @request
                PUT /object/@object_id/instance/@instance_id
        '''
        result = self.http_request(
            restful_api='/object/%s/instance/%s' % (obj, instanceid),
            method='PUT',
            data=json.dumps(data),
            headers=self.easy_headers
        )
        return 0, result


class DataAnaly(object):
    def motherboardDate(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.5.4.300.50.1.7.1.1 = STRING: "04/13/2016"'
        data_list = data.split("\"")
        get_date_list = data_list[1].split("/")
        date_str = get_date_list[2] + "-" + get_date_list[0] + "-" + get_date_list[1]
        return date_str

    def manufacturer(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.2.1.1.4.0 = STRING: "Dell Inc."'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def firmwareVersion(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.2.1.1.5.0 = STRING: "2.50.50.50"'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def deviceName(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.5.4.300.10.1.15.1 = STRING: "DCBUSIESX001.galc.com.cn"'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def deviceNumber(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.5.1.3.2.0 = STRING: "HY0JFD2"'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def shortName(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.2.1.1.2.0 = STRING: "iDRAC8"'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def serviceNumber(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.5.1.3.3.0 = STRING: "24868342118"'
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def elapsedtTime(self, data):
        # data = 'SNMPv2-SMI::enterprises.674.10892.5.2.5.0 = INTEGER: 42651763'
        data_list = data.split("INTEGER: ")
        result = int(data_list[1])
        return result

    def chassisModelModular(self, data):
        # SNMPv2-SMI::enterprises.674.10892.5.1.2.3.0 = STRING: "PowerEdge M1000e"
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def systemBladeSlotNumber(self, data):
        # SNMPv2-SMI::enterprises.674.10892.5.1.3.5.0 = STRING: "5"
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def racURL(self, data):
        # SNMPv2-SMI::enterprises.674.10892.5.1.1.6.0 = STRING: "https://192.166.16.202:443"
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def systemFQDN(self, data):
        # SNMPv2-SMI::enterprises.674.10892.5.1.3.1.0 = STRING: "DCDMZESX005.galc.com.cn"
        data_list = data.split("\"")
        result = data_list[1]
        return result

    def cpuInfo(self, data):
        result = []
        cpu_list = re.findall("674.10892.5.4.1100.30.1.26.1", data)
        # 处理器设备的标准设备描述符
        cpunum = len(cpu_list)  # 插槽
        for i in range(1, cpunum + 1):
            i = str(i)
            content = {"slotNumber": i, "physicalCores": 0, "modelName": "", "threadCore": 0}  # 插槽编号
            try:
                re_cmd = "674.10892.5.4.1100.30.1.17.1." + i + " = INTEGER: (\d+)"
                re_numberOfCores = re.search(re_cmd, data)
                physicalCores = re_numberOfCores.group(1)
                content["physicalCores"] = physicalCores  # 物理核数

                re_modelName = '674.10892.5.4.1100.30.1.23.1.' + i + ' = STRING: "([\s\S]+?)"'
                modelName = re.search(re_modelName, data).group(1)
                content["modelName"] = modelName  # cpu型号信息

                re_threadCore = '674.10892.5.4.1100.30.1.19.1.' + i + ' = INTEGER: (\d+)'
                threadCore = re.search(re_threadCore, data).group(1)
                content["threadCore"] = threadCore  # 线程数
            except Exception as e:
                pass
            result.append(content)
        # [{'physicalCores': '12', 'modelName': 'Intel(R) Xeon(R) CPU E5-2650 v4 @ 2.20GHz', 'slotNumber': '1',
        #   'threadCore': '24'},]
        return result

    def memoryInfo(self, data):
        # slotNumber 插槽编号
        # memorySize 内存大小
        # memoryFreq  内存频率
        # memoryDie  内存型号
        # memoryFactor 内存厂家
        result = []
        memory_list = re.findall('674.10892.5.4.1100.50.1.8.1.\d+ = STRING: "([\s\S]+?)"', data)
        # 定义了存储设备位置
        memory_cont = len(memory_list)
        for i in range(1, memory_cont + 1):
            slotNumber = memory_list[i - 1]
            i = str(i)
            content = {"slotNumber": slotNumber, "memorySize": '', "memoryFreq": '', "memoryDie": '',
                       'memoryFactor': ''}
            try:
                re_cmd = '.674.10892.5.4.1100.50.1.14.1.{} = INTEGER: (\d+)'.format(i)
                re_memorySize = re.search(re_cmd, data)
                memorySize = re_memorySize.group(1)
                memorySize = int(memorySize) // 1048576
                memorySize = str(memorySize) + 'g'

                re_cmd = '674.10892.5.4.1100.50.1.15.1.{} = INTEGER: (\d+)'.format(i)
                re_memoryFreq = re.search(re_cmd, data)
                memoryFreq = re_memoryFreq.group(1) + 'MHz'

                re_cmd = '674.10892.5.4.1100.50.1.22.1.{} = STRING: "([\s\S]+?)"'.format(i)
                re_memoryDie = re.search(re_cmd, data)
                memoryDie = re_memoryDie.group(1)

                re_cmd = '674.10892.5.4.1100.50.1.21.1.{} = STRING: "([\s\S]+?)"'.format(i)
                re_memoryFactor = re.search(re_cmd, data)
                memoryFactor = re_memoryFactor.group(1)

                content = {"slotNumber": slotNumber, "memorySize": memorySize, "memoryFreq": memoryFreq,
                           "memoryDie": memoryDie, 'memoryFactor': memoryFactor}

            except Exception as e:
                pass
            result.append(content)
        return result

    def diskInfo(self, data):
        # slotNumber 插槽
        # vendor   供应商  SEAGATE
        # product  型号  ST300MP0026
        # productRevisionLevel 产品版本标识 vt31
        # driveSerialNumber   驱动器序列号  WAE034KF
        # productYear 产品年份
        result = []
        re_cmd = '674.10892.5.5.1.20.130.4.1.2.\d = STRING: "([\s\S]+?)"'
        # 物理磁盘的名称
        disk_list = re.findall(re_cmd, data)
        disk_cont = len(disk_list)
        for i in range(1, disk_cont + 1):
            slotNumber = disk_list[i - 1]
            i = str(i)
            content = {"slotNumber": slotNumber, "vendor": '', "product": '', "productRevisionLevel": '',
                       'driveSerialNumber': '', "productYear": ""}
            try:
                re_cmd = '674.10892.5.5.1.20.130.4.1.3.{} = STRING: "(\w+?)"'.format(i)
                re_vendor = re.search(re_cmd, data)
                vendor = re_vendor.group(1)

                re_cmd = '674.10892.5.5.1.20.130.4.1.6.{} = STRING: "(\w+?)"'.format(i)
                re_product = re.search(re_cmd, data)
                product = re_product.group(1)

                re_cmd = '674.10892.5.5.1.20.130.4.1.8.{} = STRING: "(\w+?)"'.format(i)
                re_productRevisionLevel = re.search(re_cmd, data)
                productRevisionLevel = re_productRevisionLevel.group(1)

                re_cmd = '674.10892.5.5.1.20.130.4.1.7.{} = STRING: "(\w+?)"'.format(i)
                re_driveSerialNumber = re.search(re_cmd, data)
                driveSerialNumber = re_driveSerialNumber.group(1)

                re_cmd = '674.10892.5.5.1.20.130.4.1.34.{} = STRING: "(\d+?)"'.format(i)
                re_productYear = re.search(re_cmd, data)
                productYear = re_productYear.group(1)

                content = {"slotNumber": slotNumber, "vendor": vendor, "product": product,
                           "productRevisionLevel": productRevisionLevel,
                           'driveSerialNumber': driveSerialNumber, "productYear": productYear}

            except Exception as e:
                pass
            result.append(content)
        return result

    def networkInfo(self, data):
        # slotNumber 槽位  1
        # networkDeviceProductInfo  网卡产品信息
        # networkDevicePermanentMACAddress  机箱分配网卡（永久网卡）
        # networkDeviceCurrentMACAddress   服务分配网卡（当前网卡）
        result = []
        network_list = re.findall('674.10892.5.4.1100.90.1.6.1.\d = STRING: "([\s\S]+?)"', data)
        network_count = len(network_list)
        for i in range(1, network_count + 1):
            networkDeviceProductInfo = network_list[i - 1]
            i = str(i)
            content = {"slotNumber": i, "networkDeviceProductInfo": networkDeviceProductInfo,
                       "networkDevicePermanentMACAddress": '', "networkDeviceCurrentMACAddress": ''}
            try:
                re_cmd = 'SNMPv2-SMI::enterprises.674.10892.5.4.1100.90.1.16.1.{} = Hex-STRING: ([\s\S]+?)\n'.format(i)
                re_networkDevicePermanentMACAddress = re.search(re_cmd, data)
                networkDevicePermanentMACAddress = re_networkDevicePermanentMACAddress.group(1)
                content["networkDevicePermanentMACAddress"] = networkDevicePermanentMACAddress
                re_cmd = 'SNMPv2-SMI::enterprises.674.10892.5.4.1100.90.1.15.1.{} = Hex-STRING: ([\s\S]+?)\n'.format(i)
                re_networkDeviceCurrentMACAddress = re.search(re_cmd, data)
                networkDeviceCurrentMACAddress = re_networkDeviceCurrentMACAddress.group(1)
                content["networkDeviceCurrentMACAddress"] = networkDeviceCurrentMACAddress
            except Exception as e:
                pass
            result.append(content)
        return result


#  [{u'ctime': u'2020-05-21 10:22:23', u'outOfBandIP': u'192.166.16.202', u'creator': u'sysadmin', u'instanceId': u'5a61f2ed6f14d', u'_ts': 1590027743, u'_version': 1, u'HOST': [], u'_object_id': u'OUT_OF_BAND_MANAGEMENT', u'org': 3120, u'_object_version': 15, u'name': u'BF9YVL2'}]
def thread_work(data):
    for outband_isintance in data:
        # 查询某个ip的信息并且将相关信息传到后台
        ip = outband_isintance["outOfBandIP"]
        instanceId = outband_isintance["instanceId"]
        test_cmd = 'snmpwalk -v 2c -c {0} {1} 1.3.6.1.4.1.674.10892.5.4.300.50.1.7.1.1'.format(community, ip)
        connect_status = os.system(test_cmd)
        if connect_status != 0:
            print '{}连接不通,跳过该采集'.format(ip)
            continue
        update_dict = {"outOfBandIP": ip}
        for temp, oid in oids.items():
            try:
                cmd = 'snmpwalk -v 2c -c {0} {1} {2}'.format(community, ip, oid)
                command = os.popen(cmd)
                str_data = command.read()
                result = getattr(DataAnaly(), temp)(str_data)
                update_dict.setdefault(temp, result)
            except Exception as e:
                print e

        status = out_band.put_cmdb_instance("OUT_OF_BAND_MANAGEMENT", instanceId, update_dict)
        print status


if __name__ == "__main__":

    EASYOPS_CMDB_HOST = "192.166.14.162"
    EASYOPS_ORG = "3120"
    EASY_USER = "sysadmin"

    thread_workers = 10
    thread_dict = {}
    community = "Galc-idrac"
    oids = {
        "motherboardDate": "1.3.6.1.4.1.674.10892.5.4.300.50.1.7.1.1",  # 主板生产日期
        "manufacturer": "1.3.6.1.4.1.674.10892.2.1.1.4.0",  # 厂家
        "firmwareVersion": "1.3.6.1.4.1.674.10892.2.1.1.5.0",  # 固件版本
        "deviceName": ".1.3.6.1.4.1.674.10892.5.4.300.10.1.15.1",  # 机箱的主机名
        "deviceNumber": "1.3.6.1.4.1.674.10892.5.1.3.2.0",  # 设备序列号
        "shortName": "1.3.6.1.4.1.674.10892.2.1.1.2.0",  # 设备简短产品名称
        "serviceNumber": "1.3.6.1.4.1.674.10892.5.1.3.3.0",  # 设备系统服务号
        "chassisModelModular": "1.3.6.1.4.1.674.10892.5.1.2.3",  # 服务器型号
        "systemBladeSlotNumber": "1.3.6.1.4.1.674.10892.5.1.3.5",  # 刀片机插槽号
        "systemFQDN": "1.3.6.1.4.1.674.10892.5.1.3.1",  # 系统标准域名
        "racURL": "1.3.6.1.4.1.674.10892.5.1.1.6",  # 带外url
        "elapsedtTime": ".1.3.6.1.4.1.674.10892.5.2.5.0",  # 设备运行时间
        "cpuInfo": ".1.3.6.1.4.1.674.10892.5.4.1100.30.1",
        "memoryInfo": ".1.3.6.1.4.1.674.10892.5.4.1100.50.1",  # 内存大小以及数量  除以1024*1024 GB
        "diskInfo": "1.3.6.1.4.1.674.10892.5.5.1.20.130.4.1",  # 硬盘品牌以及数量
        "networkInfo": ".1.3.6.1.4.1.674.10892.5.4.1100.90.1"  # 网卡数量及传输速率以及mac地址
    }
    oid_analy = {

    }
    out_band = EasyOps(easy_host=EASYOPS_CMDB_HOST, easy_org=EASYOPS_ORG, easy_user=EASY_USER)
    out_band_dict = out_band.search_out_band_isinstances()
    out_band_list = out_band_dict["list"]
    len_out_band = len(out_band_list)

    for i in range(len_out_band):
        idx = i % thread_workers
        if thread_dict.has_key(idx):
            thread_dict[idx].append(out_band_list[i])
        else:
            thread_dict[idx] = [out_band_list[i]]
    #  {0: [{u'ctime': u'2020-05-21 10:22:23', u'outOfBandIP': u'192.166.16.202', u'creator': u'sysadmin', u'instanceId': u'5a61f2ed6f14d', u'_ts': 1590027743, u'_version': 1, u'HOST': [], u'_object_id': u'OUT_OF_BAND_MANAGEMENT', u'org': 3120, u'_object_version': 15, u'name': u'BF9YVL2'}],
    #  1: [{u'ctime': u'2020-05-21 11:49:53', u'outOfBandIP': u'192.166.16.225', u'creator': u'sysadmin', u'instanceId': u'5a62067c88803', u'_ts': 1590032993, u'_version': 1, u'HOST': [], u'_object_id': u'OUT_OF_BAND_MANAGEMENT', u'org': 3120, u'_object_version': 15, u'name': u'BF7RVL2'}]}

    threads = []
    for i, j in thread_dict.items():
        t = threading.Thread(target=thread_work, args=(j,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()
