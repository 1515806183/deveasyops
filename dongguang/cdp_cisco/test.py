# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey

monkey.patch_all()
import gevent
from gevent.pool import Pool

datas = {u'N-E06-XNGL-SW3650-3&&127.0.0.1&&ls': {'name': {'55': 'GigabitEthernet0/48', '54': 'GigabitEthernet0/47'},
                                                 'ifDescr': {'56': 'GigabitEthernet1/1/1',
                                                             '54': 'GigabitEthernet1/0/47',
                                                             '28': 'GigabitEthernet1/0/21',
                                                             '48': 'GigabitEthernet1/0/41',
                                                             '43': 'GigabitEthernet1/0/36', '60': 'StackPort1',
                                                             '61': 'StackSub-St1-1',
                                                             '62': 'StackSub-St1-2', '63': 'Vlan1', '64': 'Loopback0',
                                                             '49': 'GigabitEthernet1/0/42', '66': 'Vlan620',
                                                             '67': '620', '68': '107',
                                                             '69': 'Port-channel2', '52': 'GigabitEthernet1/0/45',
                                                             '53': 'GigabitEthernet1/0/46',
                                                             '24': 'GigabitEthernet1/0/17',
                                                             '25': 'GigabitEthernet1/0/18',
                                                             '26': 'GigabitEthernet1/0/19',
                                                             '27': 'GigabitEthernet1/0/20',
                                                             '20': 'GigabitEthernet1/0/13',
                                                             '21': 'GigabitEthernet1/0/14',
                                                             '22': 'GigabitEthernet1/0/15',
                                                             '23': 'GigabitEthernet1/0/16',
                                                             '46': 'GigabitEthernet1/0/39',
                                                             '47': 'GigabitEthernet1/0/40',
                                                             '44': 'GigabitEthernet1/0/37',
                                                             '45': 'GigabitEthernet1/0/38',
                                                             '42': 'GigabitEthernet1/0/35',
                                                             '29': 'GigabitEthernet1/0/22',
                                                             '40': 'GigabitEthernet1/0/33',
                                                             '41': 'GigabitEthernet1/0/34', '1': 'GigabitEthernet0/0',
                                                             '3': '1',
                                                             '2': 'Null0', '5': '1004', '4': '1002', '7': '1003',
                                                             '6': '1005',
                                                             '9': 'GigabitEthernet1/0/2', '8': 'GigabitEthernet1/0/1',
                                                             '51': 'GigabitEthernet1/0/44',
                                                             '13': 'GigabitEthernet1/0/6',
                                                             '65': 'Port-channel1', '12': 'GigabitEthernet1/0/5',
                                                             '59': 'GigabitEthernet1/1/4', '58': 'GigabitEthernet1/1/3',
                                                             '11': 'GigabitEthernet1/0/4', '10': 'GigabitEthernet1/0/3',
                                                             '39': 'GigabitEthernet1/0/32',
                                                             '38': 'GigabitEthernet1/0/31',
                                                             '15': 'GigabitEthernet1/0/8', '14': 'GigabitEthernet1/0/7',
                                                             '17': 'GigabitEthernet1/0/10',
                                                             '16': 'GigabitEthernet1/0/9',
                                                             '19': 'GigabitEthernet1/0/12',
                                                             '32': 'GigabitEthernet1/0/25',
                                                             '31': 'GigabitEthernet1/0/24',
                                                             '30': 'GigabitEthernet1/0/23',
                                                             '37': 'GigabitEthernet1/0/30',
                                                             '36': 'GigabitEthernet1/0/29',
                                                             '35': 'GigabitEthernet1/0/28',
                                                             '34': 'GigabitEthernet1/0/27',
                                                             '33': 'GigabitEthernet1/0/26',
                                                             '55': 'GigabitEthernet1/0/48',
                                                             '18': 'GigabitEthernet1/0/11',
                                                             '57': 'GigabitEthernet1/1/2',
                                                             '50': 'GigabitEthernet1/0/43'},
                                                 'peer_type': {'55': 1, '54': 1},
                                                 'vlan': ['1', '620'],
                                                 'peer_device': {'55': 'N-E03-XNGL-SW3560X-2.dgzq-gt.com',
                                                                 '54': 'N-E03-XNGL-SW3560X-2.dgzq-gt.com'},
                                                 'peer_ip': {'55': '14 64 00 F8 ', '54': '14 64 00 F8 '}},
         u'N-BGJK-SW3650-1&&192.168.28.28&&ls': {
             'name': {'55': 'GigabitEthernet1/0/48', '54': 'GigabitEthernet1/0/47', '31': 'GigabitEthernet0/13'},
             'ifDescr': {'56': 'GigabitEthernet1/1/1', '54': 'GigabitEthernet1/0/47', '28': 'GigabitEthernet1/0/21',
                         '48': 'GigabitEthernet1/0/41', '43': 'GigabitEthernet1/0/36', '60': 'StackPort1',
                         '61': 'StackSub-St1-1', '62': 'StackSub-St1-2', '63': 'Vlan1', '64': 'Port-channel1',
                         '49': 'GigabitEthernet1/0/42', '66': 'Vlan819', '67': '701', '68': '819', '69': '613',
                         '52': 'GigabitEthernet1/0/45', '53': 'GigabitEthernet1/0/46', '24': 'GigabitEthernet1/0/17',
                         '25': 'GigabitEthernet1/0/18', '26': 'GigabitEthernet1/0/19', '27': 'GigabitEthernet1/0/20',
                         '20': 'GigabitEthernet1/0/13', '21': 'GigabitEthernet1/0/14', '22': 'GigabitEthernet1/0/15',
                         '23': 'GigabitEthernet1/0/16', '46': 'GigabitEthernet1/0/39', '47': 'GigabitEthernet1/0/40',
                         '44': 'GigabitEthernet1/0/37', '45': 'GigabitEthernet1/0/38', '42': 'GigabitEthernet1/0/35',
                         '29': 'GigabitEthernet1/0/22', '40': 'GigabitEthernet1/0/33', '41': 'GigabitEthernet1/0/34',
                         '1': 'GigabitEthernet0/0', '3': '1', '2': 'Null0', '5': '1004', '4': '1002', '7': '1003',
                         '6': '1005',
                         '9': 'GigabitEthernet1/0/2', '8': 'GigabitEthernet1/0/1', '51': 'GigabitEthernet1/0/44',
                         '13': 'GigabitEthernet1/0/6', '65': 'Vlan613', '12': 'GigabitEthernet1/0/5',
                         '59': 'GigabitEthernet1/1/4', '58': 'GigabitEthernet1/1/3', '11': 'GigabitEthernet1/0/4',
                         '10': 'GigabitEthernet1/0/3', '39': 'GigabitEthernet1/0/32', '38': 'GigabitEthernet1/0/31',
                         '15': 'GigabitEthernet1/0/8', '14': 'GigabitEthernet1/0/7', '17': 'GigabitEthernet1/0/10',
                         '16': 'GigabitEthernet1/0/9', '19': 'GigabitEthernet1/0/12', '32': 'GigabitEthernet1/0/25',
                         '31': 'GigabitEthernet1/0/24', '30': 'GigabitEthernet1/0/23', '37': 'GigabitEthernet1/0/30',
                         '36': 'GigabitEthernet1/0/29', '35': 'GigabitEthernet1/0/28', '34': 'GigabitEthernet1/0/27',
                         '33': 'GigabitEthernet1/0/26', '55': 'GigabitEthernet1/0/48', '18': 'GigabitEthernet1/0/11',
                         '57': 'GigabitEthernet1/1/2', '50': 'GigabitEthernet1/0/43'},
             'peer_type': {'55': 1, '54': 1, '31': 1},
             'vlan': ['1', '613', '701', '819'],
             'peer_device': {'55': 'N-BGJK-SW3650-2', '54': 'N-BGJK-SW3650-2', '31': 'N-C08-WIFI-JK-SW3560G'},
             'peer_ip': {'55': 'AC 14 0D F9 ', '54': 'AC 14 0D F9 ', '31': '14 14 64 7D '}}}

dot_oid = {
    'dot1dBasePortIfIndex': '1.3.6.1.2.1.17.1.4.1.2',
    'dot1qTpFdbPort': '1.3.6.1.2.1.17.4.3.1.2',
    'dot1qTpFdbMac': '1.3.6.1.2.1.17.4.3.1.1',
}

pool = Pool(20)


def deal_data():
    # 处理mac_table,邻居信息
    cms = []
    for key, data in datas.items():
        info_list = key.split('&&')
        ip = info_list[1]
        community = info_list[2]
        vlan_list = data.get('vlan', '')
        if vlan_list:
            for vlan in vlan_list:
                for oid_k, oid_v in dot_oid.items():
                    cmd = "snmpwalk -v 2c -c {0} {1} {2}&&{3}&&{4}".format(community + "@" + str(vlan), ip, oid_v,
                                                                           oid_k, ip)

                    cms.append(cmd)

    n = 10  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
    result = [cms[i:i + n] for i in range(0, len(cms), n)]

    try:
        q = Queue(maxsize=10)
        while result:
            content = result.pop()
            t = threading.Thread(target=deal_valn, args=(content,))
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


class DotObj(object):
    def dot1dBasePortIfIndex(self, data):
        portIfDict = {"dot1dBasePortIfIndex": {}}  # portIfDict = {"1":"1",..."52":"52","53":"55"}
        if 'No Such' not in data or 'snmpwalk' not in data:
            portIfList = re.findall(r'SNMPv2-SMI::mib-2.17.1.4.1.2.(.*)', data)

            # 取出端口和接口索引的关系
            for i in portIfList:
                idx = i.split()[0]
                If_idx = i.split()[3]
                data = {str(idx): str(If_idx)}
                portIfDict["dot1dBasePortIfIndex"].update(data)
        return portIfDict

    def dot1qTpFdbMac(self, data):
        #     data =  '''
        # SNMPv2-SMI::mib-2.17.4.3.1.1.0.7.235.48.64.193 = Hex-STRING: 00 07 EB 30 40 C1
        # SNMPv2-SMI::mib-2.17.4.3.1.1.0.36.129.226.25.136 = Hex-STRING: 00 24 81 E2 19 88
        # SNMPv2-SMI::mib-2.17.4.3.1.1.0.80.86.136.35.160 = Hex-STRING: 00 50 56 88 23 A0
        # SNMPv2-SMI::mib-2.17.4.3.1.1.0.80.86.152.0.8 = Hex-STRING: 00 50 56 98 00 08

        res = {"dot1qTpFdbMac": {}}

        if 'No Such' not in data or 'snmpwalk' not in data:
            dot1qTpFdbMac = re.findall(r'SNMPv2-SMI::mib-2.17.4.3.1.1.(.*)', data)
            res["dot1qTpFdbMac"] = dot1qTpFdbMac

        # 要根据dot1dBasePortIfIndex dot1qTpFdbPort数据才能处理，所有把他放在最后数据处理
        return res

    def dot1qTpFdbPort(self, data):
        macPortDict = {"dot1qTpFdbPort": {}}
        if 'No Such' not in data or 'snmpwalk' not in data:
            macPortList = re.findall(r'SNMPv2-SMI::mib-2.17.4.3.1.2.(.*)', data)
            # 取出端口和mac地址十进制之间的关系
            for i in macPortList:
                mac_idx = i.split(' ')[0]
                port_idx = i.split(' ')[3]
                macPortDict["dot1qTpFdbPort"][mac_idx] = port_idx
        return macPortDict

def deal_valn(content):
    dotobj = DotObj()
    res = []
    for tent in content:
        data_list = tent.split('&&')
        cmd = data_list[0]
        oid_k = data_list[1]
        ip = data_list[2]
        res.append(
            pool.spawn(vlanclear, cmd, oid_k, ip))

    gevent.joinall(res)

    dataList = {}
    for v in res:
        for key, val in v.value.items():
            if not dataList.has_key(key):
                dataList[key] = []
            dataList[key].append(val)
    datas = {}
    for key, val in dataList.items():
        if not datas.has_key(key):
            datas[key] = {}
        for i in val:
            for k, v in i.items():
                res = getattr(dotobj, k)(v)
                if k == 'dot1qTpFdbMac':
                    if not datas[key].has_key(k):
                        datas[key][k] = []
                    datas[key][k].append(res[k])
                elif k == 'dot1qTpFdbPort':
                    if not datas[key].has_key(k):
                        datas[key][k] = {}
                    datas[key][k].update(res[k])
                elif k == 'dot1dBasePortIfIndex':
                    if not datas[key].has_key(k):
                        datas[key][k] = {}
                    datas[key][k].update(res[k])

    print datas


def _run_command(cmd, timeout=60):
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


def vlanclear(cmd, oid_k, ip):
    key_name = ip
    # 开始执行snmp任务
    try:
        data = _run_command(cmd, timeout=3)
    except subprocess.CalledProcessError as e:
        data = ''
    except Exception as e:
        data = ''
    return {key_name: {oid_k: data}}


if __name__ == '__main__':
    deal_data()
