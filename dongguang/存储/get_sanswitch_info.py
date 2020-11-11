#!/usr/local/easyops/python/bin/python
# -*- coding: utf-8 -*-

import paramiko
import requests
import logging
import sys
import re

reload(sys)
sys.setdefaultencoding("utf-8")

logging.basicConfig(level=logging.INFO)
# EASYOPS_CMDB_HOST = '10.0.3.50'
# EASYOPS_ORG = '6666'

CMDB_IP = EASYOPS_CMDB_HOST.split(':')[0]
ORG = EASYOPS_ORG
###SAN存储统一的账号密码
SAN_USER = ''
SAN_PASSWD = ''
SANSWITCH_ID = 'STORASWITCH'
SANSWITCH_PORT_ID = 'sanswitcport'


###CMDB处理
class EasyOps(object):
    def __init__(self, easy_host, easy_org, easy_user='easyops'):
        self.easy_host = easy_host
        self.easy_domain = 'cmdb_resource.easyops-only.com'
        self.easy_org = str(easy_org)
        self.easy_user = easy_user
        self.easy_headers = {
            'host': self.easy_domain,
            'org': self.easy_org,
            'user': self.easy_user,
            'content-Type': 'application/json'
        }
        self.cmdb_result = dict()

    def http_request(self, restful_api, method='GET', **kwargs):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=self.easy_host, restful_api=restful_api)
        try:
            response = requests.request(method, url, headers=self.easy_headers, **kwargs)
            if response.status_code == 200:
                response_json = response.json()
                if response_json['code'] == 0:
                    # logging.info(response_json['data'])
                    return response_json['data']  # success
            logging.exception("request:{},response:{}".format(url, response.text))
            return {}
        except Exception as e:
            logging.exception('request to cmdb:{0}'.format(e))
            raise e

    def update_object_instance(self, object_id, instance_id, data):
        return self.http_request(
            restful_api='/object/{object_id}/instance/{instance_id}'.format(object_id=object_id,
                                                                            instance_id=instance_id),
            method='PUT',
            json=data
        )

    def create_object_instance(self, object_id, data):
        return self.http_request(
            restful_api='/object/{}/instance'.format(object_id),
            method='POST',
            json=data
        )

    def update_or_create_instance(self, object_id, data):
        if isinstance(data, dict):
            response = self.search_object_instance(object_id, 'name', data['name'])
            if response['total'] == 1:
                re = self.update_object_instance(object_id, response['list'][0]['instanceId'], data)
                logging.info("更新模型{object_id}实例：{re}".format(object_id=object_id, re=re.get('name')))
                print "更新模型{object_id}实例：{re}".format(object_id=object_id, re=re.get('name'))
                return re
            else:
                re = self.create_object_instance(object_id, data)
                logging.info("新增模型{object_id}实例：{re}".format(object_id=object_id, re=re.get('name')))
                print "新增模型{object_id}实例：{re}".format(object_id=object_id, re=re.get('name'))
                return re
        else:
            logging.error("参数不是一个字典:{}".format(data))
            return None

    def instance_search(self, object_id, params):
        if params.has_key('page_size'):
            page_size = params['page_size']
        else:
            page_size = 1000
            params['page_size'] = page_size
        params['page'] = 1
        search_result = self.http_request(
            restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
            method='POST',
            json=params)
        if search_result.has_key('total'):
            total_instance_nums = int(search_result['total'])
        else:
            total_instance_nums = 0
            return search_result

        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 2):
                params['page'] = cur_page
                tmp_result = self.http_request(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                    method='POST',
                    json=params)
                search_result['list'] += tmp_result['list']
        return search_result

    def get_esxi(self):
        params = {
            "query": {
                "fc_port": {"$exists": True}
            },
            "fields": {
                "name": 1,
                "fc_port": 1
            }
        }
        return self.instance_search('VMHOSTHARDWAREBASIC', params)


    def get_sanport(self):
        params = {
            "query": {
                "rel_wwn": {"$exists": True}
            },
            "fields": {
                "name": 1,
                "rel_wwn": 1
            }
        }
        return self.instance_search(SANSWITCH_PORT_ID, params)

    def get_autoCollect_sanswitch(self):
        params = {
            "query": {
                "autoCollect": {"$eq": "yes"}
            },
            "fields": {
                "name": 1
            }
        }
        return self.instance_search(SANSWITCH_ID, params)

class ParamikoConn(object):
    def __init__(self, hostname, username, password):
        """初始化paramiko连接，连接失败则返回失败信息"""
        try:
            self.__client = paramiko.SSHClient()
            self.__client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.__client.connect(hostname=hostname, username=username, password=password,timeout=10)#ssh请求10s超时
        except Exception as e:
            print e

    def run_cmd(self, cmd):
        """运行命令并返回结果"""
        _stdin, _stdout, _stderr = self.__client.exec_command(cmd)
        return _stdout

    def close(self):
        """关闭连接"""
        self.__client.close()


def get_san_info(cls):
    '''
    获取SAN交换机的信息
    :param cls:
    :return:
    '''
    # 获取san本机存储的ip
    ip_cmd = 'ipaddrshow'
    ip_info = cls.run_cmd(ip_cmd)
    san_ip = ''
    for info in ip_info:
        if re.search(r"Ethernet IP Address:\s*(.*)", info, re.I):
            """172.24.15.51"""
            san_ip = re.search(r"Ethernet IP Address:\s*(.*)", info, re.I).group(1)

    # 采集san基本配置信息
    config_cmd = 'switchshow'
    config_info = cls.run_cmd(config_cmd)
    san_name = san_type = san_state = san_mode = san_role = san_id = san_wwn = port_id = ''
    port_infos = []
    port_info = []
    for info in config_info:
        if re.search(r"switchName:\s*(.*)", info, re.I):
            san_name = re.search(r"switchName:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchType:\s*(.*)", info, re.I):
            san_type = re.search(r"switchType:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchState:\s*(.*)", info, re.I):
            san_state = re.search(r"switchState:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchMode:\s*(.*)", info, re.I):
            san_mode = re.search(r"switchMode:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchRole:\s*(.*)", info, re.I):
            san_role = re.search(r"switchRole:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchId:\s*(.*)", info, re.I):
            san_id = re.search(r"switchId:\s*(.*)", info, re.I).group(1)
        if re.search(r"switchWwn:\s*(.*)", info, re.I):
            san_wwn = re.search(r"switchWwn:\s*(.*)", info, re.I).group(1)
        # print 'port inso',port_info
        info = info.split()
        port_info.append(info)
    while [] in port_info:
        port_info.remove([])
    port_temps = port_info[16:]
    # print 'port inso',port_info
    # print 'port inso',port_temps
    # 切割配置信息获取端口列表
    port_list = []
    for temps in port_temps:
        port_list.append(temps[0])
    # 获取所有端口的详细信息
    # 取出所有的wwn号与本机wwn号对比，排除本机wwn号，获取连接的wwn号
    # print 'port list',port_list
    for port in port_list:
        # print 'port is ;',port
        port_cmd = 'portshow ' + '-i ' + port
        # print 'port cmd',port_cmd
        port_info = cls.run_cmd(port_cmd)
        # print 'port info:',port_info
        wwn_list = []
        for info in port_info:
            if re.search(r"portWwn:\s*(.*)", info, re.I):
                port_wwn = re.search(r"portWwn:\s*(.*)", info, re.I).group(1)
            if re.search(r"portId:\s*(.*)", info, re.I):
                port_id = re.search(r"portId:\s*(.*)", info, re.I).group(1)
            if re.search(r"[\s\S]\s*(\w+:\w+:\w+:\w+:\w+:\w+:\w+:\w+)", info, re.I):
                rel_wwn = re.search(r"(\w+:\w+:\w+:\w+:\w+:\w+:\w+:\w+)", info, re.I).group(1)
                if rel_wwn == port_wwn:
                    continue
                else:
                    wwn_list.append(rel_wwn)
        port_dict = {
            'port_num': port,
            'port_id': san_ip + "_" + port_id,
            'rel_wwn': str(' '.join(wwn_list))
        }
        port_infos.append(port_dict)

    # 获取san本机存储的ip
    # ip_cmd = 'ipaddrshow'
    # ip_info = cls.run_cmd(ip_cmd)
    # san_ip = ''
    # for info in ip_info:
    # if re.search(r"Ethernet IP Address:\s*(.*)", info, re.I):
    # san_ip = re.search(r"Ethernet IP Address:\s*(.*)", info, re.I).group(1)

    # 获取san的版本和Linux内核
    version_cmd = 'version'
    version_info = cls.run_cmd(version_cmd)
    san_kernel = san_version = ''
    for info in version_info:
        if re.search(r"Kernel:\s*(.*)", info, re.I):
            san_kernel = re.search(r"Kernel:\s*(.*)", info, re.I).group(1)
        if re.search(r"Fabric OS:\s*(.*)", info, re.I):
            san_version = re.search(r"Fabric OS:\s*(.*)", info, re.I).group(1)

    # 获取风扇信息
    fan_cmd = 'fanshow'
    fan_info = cls.run_cmd(fan_cmd)
    fan_list = []
    fan_num = []
    fan_speed = []
    for info in fan_info:
        if re.search(r"Fan (.*) is Ok", info, re.I):
            num = re.search(r"Fan (.*) is Ok", info, re.I).group(1)
            fan_num.append(num)
        if re.search(r"speed is (.*)", info, re.I):
            speed = re.search(r"speed is (.*)", info, re.I).group(1)
            fan_speed.append(speed)
    for x in zip(fan_num, fan_speed):
        fan_list.append({
            'num': x[0],
            'speed': x[1]
        })

    # 获取电源信息
    power_cmd = 'psshow'
    power_info = cls.run_cmd(power_cmd)
    power_list = []
    info_list = []
    power_num = []
    for info in power_info:
        if re.search(r"Power Supply (.*) is OK", info, re.I):
            num = re.search(r"Power Supply (.*) is OK", info, re.I).group(1)
            power_num.append(num)

        info = re.split(r'[,\s]', info)
        info = filter(None, info)
        info_list.append(info)
    while [] in info_list:
        info_list.remove([])
    for x in power_num:
        power_list.append({'power_num': x})

    san_dict = {
        'name': san_ip + "_" + san_name,
        'type': san_type,
        'state': san_state,
        'mode': san_mode,
        'role': san_role,
        'id': san_id,
        'ip': san_ip,
        'wwn': san_wwn,
        'kernel': san_kernel,
        'version': san_version,
        'fan': fan_list,
        'power': power_list,
        'ports': port_infos
    }
    return san_dict


def get_sanport_info(cls):
    '''
    获取SAN交换机端口的信息
    :param cls:
    :return:
    '''
    # 获取san本机存储的ip
    ip_cmd = 'ipaddrshow'
    ip_info = cls.run_cmd(ip_cmd)
    san_ip = ''
    for info in ip_info:
        if re.search(r"Ethernet IP Address:\s*(.*)", info, re.I):
            """172.24.15.51"""
            san_ip = re.search(r"Ethernet IP Address:\s*(.*)", info, re.I).group(1)

    """获取san端口信息"""
    port_list = []
    config_cmd = 'switchshow'
    config_info = cls.run_cmd(config_cmd)
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
        port_info = cls.run_cmd(port_cmd)
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
            'name': san_ip + "_" + port_id,
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


def sanport2esxi(cmdb):
    """san交换机端口和esxi的关系"""
    logging.info('[CREATE RELATION]create relation between esxi and san_port')
    san_port_list = cmdb.get_esxi()
    esxi_list = cmdb.get_sanport()
    wwn_dict = {}
    for esxi in esxi_list:
        try:
            logging.info('[CREATE RELATION]get esxi {}'.format(esxi.get('name')))
            if esxi.get('fc_port'):
                for esxi_wwn in esxi.get('fc_port'):
                    wwn = esxi_wwn.get('wwn')
                    wwn_dict.setdefault(wwn,[]).append(esxi.get('instanceId'))
        except Exception as e:
            logging.error('[CREATE RELATION] get esxi error:{}'.format(e))
    logging.debug('[CREATE RELATION]wwn:instanceId:{}'.format(wwn_dict))
    for san_port in san_port_list:
        try:
            san_port_wwn = san_port.get('rel_wwn')
            logging.info('[CREATE RELATION]wwn is {}'.format(san_port_wwn))
            san_port_id = san_port.get('instanceId')
            if san_port_wwn:
                esxi_id_list = wwn_dict.get(san_port_wwn)
            if esxi_id_list:
                data = {
                    'VMHOSTHARDWAREBASIC':esxi_id_list
                }
                re = cmdb.update_object_instance(SANSWITCH_PORT_ID,san_port_id,data)
                logging.info('[CREATE RELATION]create san_port {name} and esxi {list} succeed'.format(name=re.get('name'),list=re.get('VMHOSTHARDWAREBASIC'))
        except Exception as e:
            logging.error('[CREATE RELATION]{}'.format(e))


def main():
    cmdb = EasyOps(CMDB_IP, ORG)
    sanswitch_list = cmdb.get_autoCollect_sanswitch()
    all_sanswitch_ip = []
    if sanswitch_list and sanswitch_list.get('list'):
        sanswitchs = sanswitch_list.get('list')
        for sanswitch in sanswitchs:
             if sanswitch.get('name'):
                 all_sanswitch_ip.append(sanswitch.get('name'))
        logging.info('[Get {num} autoCollect sanswitch] {all_sanswitch_ip}'.format(num=len(all_sanswitch_ip),all_sanswitch_ip=all_sanswitch_ip))
    else:
        logging.error('Not found any autoCollect sanswitch.')
        sys.exit(0)

    for SAN_IP in all_sanswitch_ip:
        try:
            port_id_list = []
            ###SAN交换机采集
            logging.info('[SANSWITCH] {} collecting start...'.format(SAN_IP))
            client = ParamikoConn(SAN_IP,SAN_USER,SAN_PASSWD)##连接光纤交换机
            san_info = get_san_info(client)
            re = cmdb.update_or_create_instance(SANSWITCH_ID,san_info)
            san_id = re.get('instanceId')
            logging.debug('[SANSWITCH] {ip} INFO:{re}'.format(ip=SAN_IP,re=re))
            logging.info('[SANSWITCH] {} collecting succeed.'.format(SAN_IP))

            ###SAN交换机端口采集
            logging.info('[SANSWITCH_PORT] {} port collecting start...'.format(SAN_IP))
            san_port_info_list = get_sanport_info(client)
            for san_port_info in san_port_info_list:
                san_port_info['sanport_STORASWITCH']=[san_id]#端口与设备建立关系
                re = cmdb.update_or_create_instance(SANSWITCH_PORT_ID, san_port_info)
                if re.get('instanceId'):
                    port_id_list.append(re.get('instanceId'))
                logging.debug('[{ip}SANSWITCH_PORT] {port_name} info:{info}'.format(ip=SAN_IP,port_name=san_port_info.get('name'),info=re))
            logging.info('[SANSWITCH_PORT] {} collecting succeed.'.format(SAN_IP))
        except Exception as e:
            logging.error(e)

    ###建立SAN交换机端口和宿主机关系
    sanport2esxi(cmdb)


if __name__ == '__main__':
    main()