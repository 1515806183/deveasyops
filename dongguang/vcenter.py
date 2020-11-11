# /usr/local/eaasyops/python/bin/python
# -*- coding: utf-8 -*-
# author:chenxi
# from tools import cli

import ssl
import pprint
import subprocess
import re
import getpass
import traceback
import urllib
import platform
import yaml
import socket
import datetime
import atexit
import requests
import logging
import json
import sys
import collections
import os

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect

ssl._create_default_https_context = ssl._create_unverified_context

port = 443
CMDB_IP = '192.168.213.213'

ORG = 9070
# tmp_name = ""
exc = []

# poolid=""
# disable  urllib3 warnings
if hasattr(requests.packages.urllib3, 'disable_warnings'):
    requests.packages.urllib3.disable_warnings()

# create logger object
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create a file handler
logger_handler = logging.StreamHandler(stream=sys.stdout)
logger_handler.setLevel(logging.DEBUG)

# create a logging format
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(lineno)d] %(message)s', '%Y-%m-%d %H:%M:%S')
logger_handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(logger_handler)


class RequestAPI(object):

    def __init__(self, ip, org):
        # self.host = host
        self.org = org
        self.ip = ip
        self.page_size = 1000

    def init_http_headers(self):
        """
        初始化访问http headers
        :rtype dict
        :return: headers
        """
        headers = {
            # 'host': 'cmdb.easyops-only.com',
            'host': 'cmdb_resource.easyops-only.com',
            'content-type': 'application/json',
            'user': 'easyops',
            'org': str(self.org),
        }

        return headers

    def init_http_headers_1(self):
        """
        初始化访问http headers
        :rtype dict
        :return: headers
        """
        headers = {
            'host': 'cmdb_resource.easyops-only.com',
            'content-type': 'application/json',
            'user': 'easyops',
            'org': str(self.org),
        }

        return headers

    def init_http_url(self, api, instance_id=None):
        """
        :param api: CMDB的api路径
        :param instance_id: 访问的实例ID
        :return: 返回构建的url
        """
        if instance_id:
            url = 'http://' + self.ip + api + instance_id
        else:
            url = 'http://' + self.ip + api
        url = urllib.quote(url, safe='/:?=&')
        return url

    def api_request(self, method, api, params=None):
        """
        自定义cmdb的访问方法和api
        :param method: http访问方法
        :param api: 访问apijs
        :param params: 额外参数，一般用于高级查询中的条件输入
        :rtype: dict
        :return: 返回查询结果
        """
        print '--------------'
        print params
        print '---------------'
        headers = self.init_http_headers()
        url = self.init_http_url(api)

        try:
            r = requests.request(method=method, url=url, headers=headers, json=params)

            if r.status_code == 200:
                js = r.json()

                if int(js['code']) == 0:
                    return js
                else:
                    logger.error('Error: %s' % js)
                    return None
            else:
                logger.error('Error: %s, %s' % (url, r.text))
                return None

        except Exception as e:
            print(e)
            return None

    def cmdb_get(self, api, params=None):
        # _cmdb_res = self.api_request('get', api, params=params)
        _cmdb_res = self.api_request('post', api, params=params)
        if isinstance(_cmdb_res, dict):
            if 'list' in _cmdb_res['data'].keys() and 'total' in _cmdb_res['data'].keys():
                total = int(_cmdb_res['data']['total'])
                page = int(_cmdb_res['data']['page'])
                return _cmdb_res['data']['list'], self.__next_page(total, page)
        else:
            logger.error('get res is not dict: %s' % _cmdb_res)

    def cmdb_post(self, api, params=None):
        _cmdb_res = self.api_request('post', api, params)
        if isinstance(_cmdb_res, dict):
            pass

    def __next_page(self, total, page):
        """
        翻页判断
        :param total: 页面总数
        :param page: 起始页
        :return:
        """
        page_size = self.page_size
        # 起始页*页内数量 大于或者等于总数，说明不用分页，反之亦然。
        if page * page_size >= total:
            return False
        return True

    def __cmdb_init_get_instance_api(self, obj_id, page=1):
        return  '/object/{0}/instance/_search'.format(obj_id)
        # return '/object/{0}/instance?page={1}&page_size={2}'.format(obj_id, page, self.page_size)

    def cmdb_instance_get(self, obj_id, page=1):
        _api = self.__cmdb_init_get_instance_api(obj_id, page)

        # 东莞证券两个机房，这里增加一个属性字段来区分
        params = {
            "query": {
                "idc_type": {
                    "$eq": idc_type
                }
            }
        }
        return self.cmdb_get(_api, params=params)

    def cmdb_instance_search(self, obj_id, params=None):
        _api = '/object/{0}/instance/_search'.format(obj_id, params)
        return self.api_request('post', _api, params=params)

    def create_cmdb_relation(self, relation_id, params):
        _api = '/object_relation/{0}/_autodiscovery'.format(relation_id, params)
        return self.api_request('post', _api, params=params)

    def cmdb_instance_get_all(self, obj_id):
        """
        获取对象所有实例信息
        :rtype list
        :param obj_id: 对象ID
        :return:
        """
        results = []
        page = 1
        while True:
            result = self.cmdb_instance_get(obj_id, page)
            if result:
                results.extend(result[0])
                if not result[1]:
                    break
                page += 1
            else:
                break
        return results

    def cmdb_relation_create(self, obj_id, relation_side_id, params):
        _api = '/object/{0}/relation/{1}/append'.format(obj_id, relation_side_id)

        return self.api_request('post', _api, params)

    #
    #     return self.api_request('post', _api, params)
    #
    def cmdb_instance_create(self, obj_id, params=None):
        _api = '/object/@object_id/instance/_search'.format(obj_id)
        return self.api_request('post', _api, params)

    def cmdb_create(self, obj_id, params):
        _api = '/object/{0}/instance/_import'.format(obj_id)
        return self.api_request('post', _api, params)

    def check_(self, obj_id, key_name):
        results = []
        page = 1
        page_size = 1000
        params = {
            'page': page,
            'page_size': page_size,
            "query": {
                "name": {
                    "$eq": key_name
                }
            }
        }
        print params
        _api = _api = '/object/{0}/instance/_search'.format(obj_id)
        while True:

            result = self.api_request('post', _api, params)
            if len(result['data']['list']) == 0:
                break
            else:
                page += 1
                params['page'] = page
                for i in result['data']['list']:
                    results.append(i)
        return results


####数据中心
def get_datacenter(content, key, poolid):
    data = {}
    datas = []
    key = []

    re = RequestAPI(CMDB_IP, ORG)
    listOBJ = get_obj(content, key)
    children = content.rootFolder.childEntity
    # print children.pop()

    res = {}
    clust_list = []

    for child in children:  # Iterate though DataCenter
        dcenter = {}
        pools = []
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['dataCenterId'] = str(child).split(':')[1].replace('\'', '')
        dcenter['dataCenterName'] = child.name
        pools.append(poolid)
        dcenter['poolid'] = pools
        # res = {'regiht': dcenter['name'], "leght": [poolid]}
        datas.append(dcenter)

        data['keys'] = ['name']
        data['datas'] = datas

    re.cmdb_create('VMWARE_DATACENTER', data)

    cl_list = []

    for childss in children:  # Iterate though DataCenters
        clust_list = []
        clustss = {}
        re_list = []
        chname = poolid + "_" + str(childss).split(':')[1].replace('\'', '')
        # 数据中心和资源池关联
        print "开始采集数据中心和资源池的关系"
        ress = {'regiht': chname, "leght": [poolid]}
        print json.dumps(ress), '............................'
        create_instance_list('VMWARE_DATACENTER_RESOURCE_POOL_VMWARE_DATACENTER_RESOURCE_POOL', 'VMWARE_DATACENTER',
                             ress)
        print "数据中心和资源池的关系采集完毕"
        print "-----------------------------------"

        if "Folder" not in str(childss):
            for cluster in childss.hostFolder.childEntity:
                clname = poolid + "_" + str(cluster).split(':')[1].replace('\'', '')
                # 数据中心和集群的关系
                clust_list.append(clname)
            print "开始采集数据中心和集群的关系"
            clustss = {'regiht': chname, "leght": clust_list}
            create_instance_list('VMWARE_DATACENTER_VMWARE_CLUSTER_VMWARE_DATACENTER_VMWARE_CLUSTER',
                                 'VMWARE_DATACENTER',
                                 clustss)
            print "数据中心和集群的关系采集完毕"
            print "-----------------------------------"


def get_obj(content, vim_type, name=None):
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vim_type, True)

    if name:
        for c in container.view:

            if c.name == name:
                obj = c
                return [obj]
    else:
        return container.view


####esxi主机信息
def get_host(content, key, poolid):
    listOBJ = get_obj(content, key)
    re = RequestAPI(CMDB_IP, ORG)
    datas = []
    data = {}
    vm_list = []
    vms = {}

    for each in listOBJ:

        # for i in each.network:
        dcenter = {}
        vm_id = []
        # tupleVNic = sys._getframe().f_code.co_name, index, each.config.network.vnic
        ips = []
        for i in each.config.network.vnic:
            ip_list = {}
            if "." in i.spec.ip.ipAddress:
                if i.spec.ip.ipAddress != "169.254.1.1":
                    ip_list = {"ip": i.spec.ip.ipAddress, "mac": i.spec.mac.upper()}
                    ips.append(ip_list)
                    dcenter['ipaddr'] = i.spec.ip.ipAddress
        pnic_version = each.summary.config.product.fullName

        vnic = each.config.network.vnic[0]
        vnic_mac = vnic.spec.mac.upper()
        vnic_ip = vnic.spec.ip.ipAddress

        pnics = each.config.network.pnic
        eth = []
        for pnic in pnics:
            if pnic.linkSpeed:
                speed = pnic.linkSpeed.speedMb
                status = 'on'
            else:
                status = 'down'
                speed = 0
            tmp = {
                "name": pnic.device,
                "mac": pnic.mac.upper(),
                "speed": speed,
                "status": status
            }
            eth.append(tmp)

        mem = each.summary.hardware.memorySize / 1024 / 1024

        dcenter['ip'] = ips
        dcenter['eth'] = eth
        dcenter['name'] = poolid + "_" + str(each).split(':')[1].replace('\'', '')
        dcenter['hostid'] = str(each).split(':')[1].replace('\'', '')
        dcenter['version'] = pnic_version
        dcenter['hostname'] = each.summary.config.name
        dcenter['connected'] = each.summary.runtime.powerState
        dcenter['maintenance'] = str(each.summary.runtime.inMaintenanceMode)
        dcenter['numCpuCores'] = each.summary.hardware.numCpuCores
        dcenter['cpuMhz'] = each.summary.hardware.cpuMhz
        dcenter['overallCpuUsage'] = each.summary.quickStats.overallCpuUsage
        dcenter['overallMemoryUsage'] = each.summary.quickStats.overallMemoryUsage
        dcenter['memorySize'] = mem
        dcenter['producer'] = each.summary.hardware.vendor
        datas.append(dcenter)
    data['keys'] = ['name']
    data['datas'] = datas

    re.cmdb_create('VMWARE_HOST_COMPUTER', data)

    for each in listOBJ:
        eaname = poolid + "_" + str(each).split(':')[1].replace('\'', '')
        vm_list = []
        for vms in each.vm:
            # 关联虚拟机id
            vmsname = poolid + "_" + str(vms).split(':')[1].replace('\'', '')
            # vms =
            vm_list.append(vmsname)
        # 宿主机关联所有虚拟机
        print "开始采集宿主机关联所有虚拟机"
        vmss = {'regiht': eaname, "leght": vm_list}
        create_instance_list('VMWARE_HOST_COMPUTER_VMWARE_VIRTUAL_MACHINE_VMWARE_HOST_COMPUTER_VMWARE_VIRTUAL_MACHINE',
                             'VMWARE_HOST_COMPUTER', vmss)
        print "宿主机关联所有虚拟机采集完毕"
        print "-----------------------------------"


###存储计算换算G，TB
def sizeof_fmt(num):
    for item in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%0.1f%s" % (num, item)
        num /= 1024.0
    return "%f%s" % (num, 'TB')
    # return "%3.1f" % (num)


#####存储
def get_datastore(content, key, poolid):
    listOBJ = get_obj(content, key)
    data = {}
    datas = []

    re = RequestAPI(CMDB_IP, ORG)

    for child in listOBJ:  # Iterate though DataCenters
        dcenter = {}
        host_id = []
        vm_id = []
        hostss = {}
        host_list = []
        vmss = {}
        vm_list = []

        ds_capacity = child.summary.capacity / 1024 / 1024
        ds_freespace = child.summary.freeSpace / 1024 / 1024
        ds_uncommitted = child.summary.uncommitted if child.summary.uncommitted else 0
        ds_provisioned = ds_capacity - ds_freespace + ds_uncommitted
        ds_overp = ds_provisioned - ds_capacity
        ds_overp_pct = (ds_overp * 100) / ds_capacity \
            if ds_capacity else 0
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['id'] = str(child).split(':')[1].replace('\'', '')
        dcenter['url'] = format(child.summary.url)
        dcenter['freespace'] = ds_freespace  # format(sizeof_fmt(ds_freespace))
        # dcenter['vcenter_datastore_allocated'] = format(sizeof_fmt(ds_provisioned))
        dcenter['capacity'] = ds_capacity  # format(sizeof_fmt(ds_capacity))
        # dcenter['ds_uncommitted'] = format(sizeof_fmt(ds_uncommitted))

        # dcenter['type'] = child.summary.type
        dcenter['storename'] = child.summary.name
        dcenter['multiple_host_access'] = 'True'

        datas.append(dcenter)
    data['keys'] = ['name']
    data['datas'] = datas
    re.cmdb_create('VMWARE_DATASTORE', data)

    for childs in listOBJ:
        host_list = []
        vm_list = []
        vm_id = []
        host_id = []
        gourname = poolid + "_" + str(childs).split(':')[1].replace('\'', '')
        for vms in childs.vm:
            # 关联虚拟机id
            # print len(childs.vm)
            vm_name = poolid + "_" + str(vms).split(':')[1].replace('\'', '')
            vm_list.append(vm_name)
        vmss = {'regiht': gourname, "leght": vm_list}

        # 端口组与虚拟机关系

        print "开始采集存储关联所有虚拟机"
        create_instance_list('VMWARE_DATASTORE_VMWARE_VIRTUAL_MACHINE_VMWARE_DATASTORE_VMWARE_VIRTUAL_MACHINE',
                             'VMWARE_DATASTORE', vmss)
        print "存储组关联所有虚拟机采集完毕"
        print "-----------------------------------"

        for hosts in childs.host:
            # 关联虚拟机id

            host_name = poolid + "_" + str(hosts).split(':')[1].replace('\'', '')
            host_list.append(host_name)
        hostss = {'regiht': gourname, "leght": host_list}

        print "开始采集存储关联所有宿主机"
        create_instance_list('VMWARE_DATASTORE_VMWARE_HOST_COMPUTER_VMWARE_DATASTORE_VMWARE_HOST_COMPUTER',
                             'VMWARE_DATASTORE', hostss)
        print "存储关联所有宿主机采集完毕"
        print "-----------------------------------"


###资源池
def get_resourcepool(content, key, poolid):
    listOBJ = get_obj(content, key)
    data = {}
    datas = []
    key = []

    re = RequestAPI(CMDB_IP, ORG)

    for child in listOBJ:  # Iterate though DataCenters
        dcenter = {}
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['id'] = str(child).split(':')[1].replace('\'', '')
        dcenter['poolname'] = child.name
        datas.append(dcenter)

    data['keys'] = ['name']
    data['datas'] = datas
    print re.cmdb_create('VMWARE_RESOURCE_POOL', data)


###端口组
def get_portgroup(content, key, poolid):
    listOBJ = get_obj(content, key)
    data = {}
    datas = []
    key = []

    re = RequestAPI(CMDB_IP, ORG)

    for child in listOBJ:  # Iterate though DataCenters
        vm_id = []
        host_id = []
        switch_id = []
        vmss = {}
        hostss = {}
        sw = {}
        sw_list = []

        dcenter = {}
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['id'] = str(child).split(':')[1].replace('\'', '')
        # print dcenter['name']
        # dcenter['portname'] = child.config.name

        # print  child.name
        # print child.config.defaultPortConfig.vlan.vlanId
        dcenter['vlan_id'] = child.config.defaultPortConfig.vlan.vlanId

        dcenter['ports'] = child.portKeys
        dcenter['numPorts'] = child.config.numPorts
        # print child.config.defaultPortConfig.vlan.vlanId,'1111111'
        child.config.distributedVirtualSwitch.uuid
        dcenter['portname'] = child.name
        dcenter['number_of_ports'] = child.config.numPorts

        # switchs = child.config.distributedVirtualSwitch
        # switch_id.append(poolid + "_" + str(switchs).split(':')[1].replace('\'', ''))
        # sw = {'regiht': dcenter['name'], "leght": switch_id}

        # sw_list.append(sw)

        datas.append(dcenter)
    ##

    data['keys'] = ['name']
    data['datas'] = datas
    #
    re.cmdb_create('VMWARE_PORT_GROUP', data)
    # 端口组与宿主机关系
    # print host_list

    for childs in listOBJ:
        host_list = []
        vm_list = []
        vm_id = []
        host_id = []

        gourname = poolid + "_" + str(childs).split(':')[1].replace('\'', '')
        for vms in childs.vm:
            # 关联虚拟机id
            # print len(childs.vm)
            vm_name = poolid + "_" + str(vms).split(':')[1].replace('\'', '')
            vm_list.append(vm_name)
        vmss = {'regiht': gourname, "leght": vm_list}

        # 端口组与虚拟机关系

        print "开始采集端口组关联所有虚拟机"
        create_instance_list('VMWARE_PORT_GROUP_VMWARE_VIRTUAL_MACHINE_VMWARE_PORT_GROUP_VMWARE_VIRTUAL_MACHINE',
                             'VCENTER_PORT_GROUP', vmss)
        print "端口组关联所有虚拟机采集完毕"
        print "-----------------------------------"

        for hosts in childs.host:
            # 关联虚拟机id

            host_name = poolid + "_" + str(hosts).split(':')[1].replace('\'', '')
            host_list.append(host_name)
        hostss = {'regiht': gourname, "leght": host_list}

        print "开始采集端口组关联所有宿主机"
        create_instance_list('VMWARE_PORT_GROUP_VMWARE_HOST_COMPUTER_VMWARE_PORT_GROUP_VMWARE_HOST_COMPUTER',
                             'VCENTER_PORT_GROUqP', hostss)
        print "宿主机关联所有宿主机采集完毕"
        print "-----------------------------------"
    # #

    # #
    # # 端口组与交换机关系
    # print "开始采集端口组关联所有交换机"
    # create_instance_list('VMWARE_PORT_GROUP_VMWARE_VIRTUAL_SWITCH_VMWARE_PORT_GROUP_VMWARE_VIRTUAL_SWITCH',
    #                      'VCENTER_PORT_GROUP', sw_list)
    # print "端口组关联所有交换机采集完毕"
    # print "-----------------------------------"


# # 获取所有的Template##################
def get_template(content, key, poolid):
    listOBJ = get_obj(content, key)

    re = RequestAPI(CMDB_IP, ORG)
    data = {}
    datas = []

    for child in listOBJ:
        dcenter = {}

        disks = []
        disk_path = {}
        a = []
        ip_list = {}
        ips = []
        if child.summary.config.template == True:
            for stack in child.guest.net:
                for i in stack.ipAddress:
                    ip_list = {'mac': stack.macAddress.upper(), 'ipaddress': i}
                    ips.append(ip_list)

            for disk_name in child.guest.disk:
                disks = []
                disk_path = {'disk_name': disk_name.diskPath, 'capacity': format(sizeof_fmt(disk_name.capacity)),
                             'freeSpace': format(sizeof_fmt(disk_name.freeSpace))}
                # disk_path['disk_name'] = disk_name.diskPath
                # disk_path['capacity'] = format(sizeof_fmt(disk_name.capacity))
                # disk_path['freeSpace'] = format(sizeof_fmt(disk_name.freeSpace))
                disks.append(disk_path)

            dcenter['uuid'] = child.summary.config.uuid
            dcenter['num_cpus'] = child.summary.config.numCpu
            dcenter['memory'] = child.summary.config.memorySizeMB
            dcenter['guest_id'] = child.summary.config.guestFullName
            dcenter['vmname'] = child.summary.config.name
            dcenter['temp_info'] = str(child.summary.config.template)
            dcenter['disk'] = disks
            dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
            dcenter['id'] = str(child).split(':')[1].replace('\'', '')
            dcenter['ip'] = child.summary.guest.ipAddress
            dcenter['network'] = ips
            dcenter['vmware_tools_status'] = child.guestHeartbeatStatus
            network = child.network
            # for i in network:
            #     data['port_group_code'] = str(i).strip("'")
            datas.append(dcenter)

    data['keys'] = ['name']
    data['datas'] = datas
    # print data
    print re.cmdb_create('VMWARE_TEMPLATE', data)


# 获取所有的虚拟机##################
def get_vm_host(content, key, poolid):
    listOBJ = get_obj(content, key)

    re = RequestAPI(CMDB_IP, ORG)
    data = {}
    datas = []

    for child in listOBJ:
        dcenter = {}

        disks = []
        disk_path = {}
        a = []
        ip_list = {}
        ips = []
        # if child.summary.config.template == False:
        for stack in child.guest.net:
            for i in stack.ipAddress:
                ip_list = {'mac': stack.macAddress, 'ipaddress': i}
                ips.append(ip_list)
        for disk_name in child.guest.disk:
            disk_path = {'disk_name': disk_name.diskPath, 'capacity': format(sizeof_fmt(disk_name.capacity)),
                         'freeSpace': format(sizeof_fmt(disk_name.freeSpace))}
            disks.append(disk_path)
        dcenter['uuid'] = child.summary.config.uuid
        dcenter['num_cpus'] = child.summary.config.numCpu
        dcenter['memory'] = child.summary.config.memorySizeMB
        dcenter['guest_id'] = child.summary.config.guestFullName
        dcenter['vmname'] = child.summary.config.name
        dcenter['temp_info'] = str(child.summary.config.template)
        dcenter['disk'] = disks
        dcenter['type'] = str(child.summary.config.template)
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['id'] = str(child).split(':')[1].replace('\'', '')
        dcenter['default_ip_address'] = child.summary.guest.ipAddress
        dcenter['network'] = ips
        dcenter['vmware_tools_status'] = child.guestHeartbeatStatus

        network = child.network
        # for i in network:
        #     data['port_group_code'] = str(i).strip("'")
        datas.append(dcenter)
    #
    data['keys'] = ['name']
    data['datas'] = datas
    # print data
    print re.cmdb_create('VMWARE_VIRTUAL_MACHINE', data)


# 获取所有的集群##################
def get_cluster(content, key, poolid):
    listOBJ = get_obj(content, key)
    re = RequestAPI(CMDB_IP, ORG)
    data = {}
    datas = []
    host_list = []
    hostss = {}
    store_list = []
    stores = {}

    for child in listOBJ:
        # print child.datastore
        dcenter = {}
        datastore = []
        hosts = []
        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['clusterid'] = str(child).split(':')[1].replace('\'', '')
        dcenter['drs_enabled'] = str(child.configuration.drsConfig.enableVmBehaviorOverrides)
        dcenter['clustername'] = child.name
        # dcenter['resource_pool_id'] = poolid + "_" + str(child.resourcePool).split(':')[1].replace('\'', '')

        for ds in child.datastore:
            datastore.append(poolid + "_" + str(ds).split(':')[1].replace('\'', ''))
            stores = {'regiht': dcenter['name'], "leght": datastore}
            store_list.append(stores)

        for syshost in child.host:
            hosts.append(poolid + "_" + str(syshost).split(':')[1].replace('\'', ''))
            hostss = {'regiht': dcenter['name'], "leght": hosts}
            host_list.append(hostss)

        datas.append(dcenter)

    data['keys'] = ['name']
    data['datas'] = datas
    # print data

    re.cmdb_create('VMWARE_CLUSTER', data)

    for child in listOBJ:
        store_list = []
        storess = {}
        stores = {}
        hostss = {}
        host_list = []
        hostsss = {}
        gourname = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        for ds in child.datastore:
            datastore_name = poolid + "_" + str(ds).split(':')[1].replace('\'', '')
            store_list.append(datastore_name)
        storess = {'regiht': gourname, "leght": store_list}
        # 集群关联所有的Esxi宿主机
        print "开始采集集群关联所有的Esxi宿主机"
        create_instance_list('VMWARE_CLUSTER_VMWARE_DATASTORE_VMWARE_CLUSTER_VMWARE_DATASTORE', 'VMWARE_CLUSTER',
                             storess)
        print "集群关联所有的Esxi宿主机采集完毕"
        print "-----------------------------------"

        for syshost in child.host:
            host_name = poolid + "_" + str(syshost).split(':')[1].replace('\'', '')
            host_list.append(host_name)
        hostss = {'regiht': gourname, "leght": host_list}
        print "开始采集集群关联所有的存储"
        create_instance_list('VMWARE_CLUSTER_VMWARE_HOST_COMPUTER_VMWARE_CLUSTER_VMWARE_HOST_COMPUTER',
                             'VMWARE_CLUSTER', hostss)
        print "集群关联所有的存储采集完毕"
        print "-----------------------------------"


# 获取交换机信息##################
def get_switch(content, key, poolid):
    listOBJ = get_obj(content, key)
    re = RequestAPI(CMDB_IP, ORG)
    data = {}
    datas = []
    vmss = {}
    vm_list = []
    for child in listOBJ:
        dcenter = {}

        vm_list = []

        host_id = []

        # for hosts in child.summary.host:
        #     # 宿主机id
        #     host_id.append(poolid + "_" + str(hosts).split(':')[1].replace('\'', ''))

        dcenter['name'] = poolid + "_" + str(child).split(':')[1].replace('\'', '')
        dcenter['id'] = str(child).split(':')[1].replace('\'', '')
        dcenter['vcname'] = child.name
        dcenter['vmid'] = vm_list

        # dcenter['hostid'] = host_id
        for vms in child.summary.vm:
            vm_list.append(poolid + "_" + str(vms).split(':')[1].replace('\'', ''))
            vmss = {'regiht': dcenter['name'], "leght": vm_list}
            vm_list.append(vmss)

        # dcenter['hostid'] = host_id
        datas.append(dcenter)
    data['keys'] = ['name']
    data['datas'] = datas
    print re.cmdb_create('VMWARE_VIRTUAL_SWITCH', data)

    # # 交换机与虚拟机关系
    # print "开始采集虚拟机关联所有交换机"
    # create_instance('VMWARE_VIRTUAL_SWITCH_VMWARE_VIRTUAL_MACHINE_VMWARE_VIRTUAL_SWITCH_VMWARE_VIRTUAL_MACHINE', 'VCENTER_SWITCH', 'vm_list')
    # print "虚拟机关联所有交换机采集完毕"
    # print "-----------------------------------"


def get_network(content, key, poolid):
    listOBJ = get_obj(content, key)
    re = RequestAPI(CMDB_IP, ORG)
    data = {}
    datas = []

    hosts = []
    vm_id = []

    for child in listOBJ:
        dcenter = {}

        dcenter['name'] = poolid + "_" + child.name
        dcenter['networkname'] = child.name
        datas.append(dcenter)

    data['keys'] = ['name']
    data['datas'] = datas
    print re.cmdb_create('VMWARE_NETWORK', data)

    for child in listOBJ:
        dcenter = {}
        dcenter['name'] = poolid + "_" + child.name
        # dcenter['networkname'] = child.name
        # datas.append(dcenter)
        for vms in child.vm:
            # 关联虚拟机id
            vm_list = []
            vm_id.append(poolid + "_" + str(vms).split(':')[1].replace('\'', ''))
            vmss = {'regiht': dcenter['name'], "leght": vm_id}
            vm_list.append(vmss)
            print "开始采集网络与虚拟机到关系"
            create_instance_list('VMWARE_NETWORK_VMWARE_VIRTUAL_MACHINE_VMWARE_NETWORK_VMWARE_VIRTUAL_MACHINE',
                                 'VMWARE_NETWORK', vm_list)
            print "网络与虚拟机到关系"
            print "-----------------------------------"

        for syshost in child.host:
            host_list = []
            hosts.append(poolid + "_" + str(syshost).split(':')[1].replace('\'', ''))
            hostss = {'regiht': dcenter['name'], "leght": hosts}
            host_list.append(hostss)
            print "开始采集网络与宿主机到关系"
            create_instance_list('VMWARE_NETWORK_VMWARE_HOST_COMPUTER_VMWARE_NETWORK_VMWARE_HOST_COMPUTER',
                                 'VMWARE_NETWORK', host_list)
            print "网络与宿主机到关系采集完毕"
            print "-----------------------------------"

    # print len(vm_list)
    # print vm_list

    #
    # data['keys'] = ['name']
    # data['datas'] = datas
    # print re.cmdb_create('VMWARE_NETWORK', data)

    #
    # print "开始采集网络与宿主机到关系"
    # create_instance_list('VMWARE_NETWORK_VMWARE_HOST_COMPUTER_VMWARE_NETWORK_VMWARE_HOST_COMPUTER', 'VMWARE_NETWORK',host_list)
    # print "网络与宿主机到关系采集完毕"
    # print "-----------------------------------"

    # print "开始采集网络与虚拟机到关系"
    # create_instance_list('VMWARE_NETWORK_VMWARE_VIRTUAL_MACHINE_VMWARE_NETWORK_VMWARE_VIRTUAL_MACHINE','VMWARE_NETWORK', vm_list)
    # print "网络与虚拟机到关系"
    # print "-----------------------------------"


def select_instance(obj_id, name=None):
    params = None
    if name:
        params = {
            "query": {
                "name": {
                    "$in": name
                }
            }
        }
    else:
        params = None
    re = RequestAPI(CMDB_IP, ORG)
    data = re.cmdb_instance_search(obj_id, params)
    return data['data']['list']


def create_instance(relation_id, obj_id, re_list):
    re = RequestAPI(CMDB_IP, ORG)
    data = []

    for res in re_list:
        print res

        da = {
            "left_instance": {
                "name": res['regiht'],
            },
            "right_instance": {
                "name": res['leght'],
            }
        }
        data.append(da)
    # po
    datas = {
        "match": {
            "left_match": ["name"],
            "right_match": ["name"]
        },
        "data": data
    }

    re.create_cmdb_relation(relation_id, datas)


def create_instance_list(relation_id, obj_id, re_list):
    re = RequestAPI(CMDB_IP, ORG)
    data = []
    for i in re_list['leght']:
        re_le = {"left_instance": {"name": re_list['regiht']}, "right_instance": {"name": i}}
        data.append(re_le)

    datas = {
        "match": {
            "left_match": ["name"],
            "right_match": ["name"]
        },
        "data": data
    }

    print re.create_cmdb_relation(relation_id, datas), '00000000000000000000000000'


def cmdb_content():
    re = RequestAPI(CMDB_IP, ORG)
    vm_re_pool = re.cmdb_instance_get('RESOURCE_POOL')
    co = []
    poolids = []
    cou = {}

    for vm in vm_re_pool[0]:
        if vm['type'] == 'vmware':
            poolid = vm['name']
            username = vm['username']
            host = vm['ip']
            passwrod = vm['password']
            si = SmartConnect(
                host=host,
                user=username,
                pwd=passwrod,
                port=port)
            # disconnect vc
            atexit.register(Disconnect, si)
            content = si.RetrieveContent()
            cou = {"con": content, "pool": poolid}
            co.append(cou)

    return co,


def create_cmdb():
    co = cmdb_content()
    for con in co[0]:
        content = con['con']
        if tmp_name == "数据中心":
            ###数据中心
            print "开始采集数据中心数据请稍后......"
            get_datacenter(content, [vim.Datacenter], con['pool'])
            print con['pool']
            print "数据中心数据采集完毕"
            print "-----------------------------------"
        elif tmp_name == "集群":
            ###集群
            print "开始采集集群数据请稍后......"
            print con['pool']
            get_cluster(content, [vim.ClusterComputeResource], con['pool'])
            print "集群数据采集完毕"
            print "-----------------------------------"

        elif tmp_name == "ESXI主机":
            ###esxi主机
            print "开始采集esxi主机数据请稍后......"
            print con['pool']
            get_host(content, [vim.HostSystem], con['pool'])
            print "esxi主机数据采集完毕"
            print "-----------------------------------"
        elif tmp_name == "存储":
            # 存储
            print "开始采集存储数据请稍后......"
            print con['pool']
            get_datastore(content, [vim.Datastore], con['pool'])
            print "存储数据采集完毕"
            print "-----------------------------------"

        elif tmp_name == "vm资源池":
            # 资源池
            print "开始采集资源池数据请稍后......"
            print con['pool']
            get_resourcepool(content, [vim.ResourcePool], con['pool'])
            print "资源池数据采集完毕"
            print "-----------------------------------"

        elif tmp_name == "端口组":
            # 端口组
            print "开始采集端口组数据请稍后......"
            print con['pool']
            # get_portgroup(content, [vim.Network], con['pool'])
            get_portgroup(content, [vim.DistributedVirtualPortgroup], con['pool'])
            print "端口组数据采集完毕"
            print "-----------------------------------"
        # elif tmp_name == "网络":
        #     # 网络
        #     print "开始采集网络数据请稍后......"
        #     # get_portgroup(content, [vim.Network], con['pool'])
        #     get_network(content, [vim.Network], con['pool'])
        #     print "网络数据采集完毕"
        #     print "-----------------------------------"

        # get_template(content,[vim.VirtualMachine])
        elif tmp_name == "虚拟机":
            # 虚拟机
            print "开始采集虚拟机数据请稍后......"
            print con['pool']
            get_vm_host(content, [vim.VirtualMachine], con['pool'])
            print "虚拟机数据采集完毕"
            print "-----------------------------------"

        # elif tmp_name == "交换机":
        #     # 交换机
        #     print "开始采集交换机数据请稍后......"
        #     print con['pool']
        #
        #     get_switch(content, [vim.DistributedVirtualSwitch], con['pool'])
        #     print "交换机数据采集完毕"
        #     print "-----------------------------------"
        # elif tmp_name == "模版":
        #     # 交换机
        #     print "开始采集模版数据请稍后......"
        #     print con['pool']
        #
        #     get_template(content, [vim.VirtualMachine], con['pool'])
        #     print "交换机模版采集完毕"
        #     print "-----------------------------------"

        else:

            # # 模版
            # print "开始采集模版数据请稍后......"
            # print con['pool']
            # get_template(content, [vim.VirtualMachine], con['pool'])
            # print "交换机模版采集完毕"
            # print "-----------------------------------"

            # 资源池
            print "开始采集资源池数据请稍后......"
            print con['pool']
            get_resourcepool(content, [vim.ResourcePool], con['pool'])
            print "资源池数据采集完毕"
            print "-----------------------------------"

            # 虚拟机
            print "开始采集虚拟机数据请稍后......"
            print con['pool']
            get_vm_host(content, [vim.VirtualMachine], con['pool'])
            print "虚拟机数据采集完毕"
            print "-----------------------------------"

            ###esxi主机
            print "开始采集esxi主机数据请稍后......"
            print con['pool']
            get_host(content, [vim.HostSystem], con['pool'])
            print "esxi主机数据采集完毕"
            print "-----------------------------------"

            # # 交换机
            # print "开始采集交换机数据请稍后......"
            # print con['pool']
            #
            # get_switch(content, [vim.DistributedVirtualSwitch], con['pool'])
            # print "交换机数据采集完毕"
            # print "-----------------------------------"

            # 端口组
            print "开始采集端口组数据请稍后......"
            print con['pool']
            get_portgroup(content, [vim.DistributedVirtualPortgroup], con['pool'])
            print "端口组数据采集完毕"
            print "-----------------------------------"

            # print "开始采集网络数据请稍后......"
            # print con['pool']
            # # get_portgroup(content, [vim.Network], con['pool'])
            # get_network(content, [vim.Network], con['pool'])
            # print "网络数据采集完毕"
            # print "-----------------------------------"

            # 存储
            print "开始采集存储数据请稍后......"
            print con['pool']
            get_datastore(content, [vim.Datastore], con['pool'])
            print "存储数据采集完毕"
            print "-----------------------------------"

            ###集群
            print "开始采集集群数据请稍后......"
            print con['pool']
            get_cluster(content, [vim.ClusterComputeResource], con['pool'])
            print "集群数据采集完毕"
            print "-----------------------------------"

            ###数据中心
            print "开始采集数据中心数据请稍后......"
            get_datacenter(content, [vim.Datacenter], con['pool'])
            print con['pool']
            print "数据中心数据采集完毕"
            print "-----------------------------------"


if __name__ == "__main__":
    create_cmdb()
