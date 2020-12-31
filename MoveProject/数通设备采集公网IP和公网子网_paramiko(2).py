# -*- coding: utf-8 -*-
import re
import datetime
import ipaddress
import urllib

import paramiko
import requests
import ast
import threading
from multiprocessing import Queue, Process, Manager
# from core.forward import Forward
import time
import traceback
import warnings
import sys

warnings.filterwarnings("ignore")

# 数通设备账号密码
DEVICE_NAME = "cmdb_col"
DEVICE_PASSWORD = "Kh&3175Wu"
# 迪普设备账号密码
DEPTCH_DEVICE_NAME = "gdinops"
DEPTCH_DEVICE_PASSWORD = "Lg71da#@B5"

pool_alias = {
    "2302": "广州黄埔区凤凰三横路中国移动A2栋三楼机房用户2",
    "2401": "广州黄埔区凤凰三横路中国移动A2栋四楼机房用户1",
    "2402": "广州黄埔区凤凰三横路中国移动A2栋四楼机房用户2",
    "2501": "广州黄埔区凤凰三横路中国移动A2栋五楼机房用户1",
    "2502": "广州黄埔区凤凰三横路中国移动A2栋五楼机房用户2",
}


class BASESSHV2(object):
    def __init__(self, ip, username, password, **kwargs):
        """Init a sshv2-like class instance, accept port/timeout/privilegePw as extra parameters
        """
        self.ip = ip
        self.username = username
        self.password = password

        self.port = kwargs['port'] if 'port' in kwargs else 22
        self.timeout = kwargs['timeout'] if 'timeout' in kwargs else 3000
        self.banner_timeout = kwargs['banner_timeout'] if 'banner_timeout' in kwargs else 6000
        self.privilegePw = kwargs['privilegePw'] if 'privilegePw' in kwargs else ''

        self.isLogin = False
        self.isEnable = False

        self.channel = ''
        self.shell = ''
        # self.basePrompt = r'(>|#|\]|\$|\)) *$'
        # Multiple identical characters may appear
        self.basePrompt = "(>|#|\]|\$) *$"
        self.prompt = ''
        self.moreFlag = '(\-)+( |\()?[Mm]ore.*(\)| )?(\-)+|\(Q to quit\)'
        self.mode = 1
        self.login_result = self.login()

        """
        - parameter ip: device's ip
        - parameter port : device's port
        - parameter timeout : device's timeout(Only for login,not for execute)
        - parameter channel: storage device connection channel session
        - parameter shell: paramiko shell, used to send(cmd) and recv(result)
        - parameter prompt: [ex][wangzhe@cloudlab100 ~]$
        """

    def __del__(self):
        # Logout after the program leaves.
        self.logout()

    def sshv2(self):
        # return SSH channel, use ssh.invoke_shell() to active a shell, and resize window size
        njInfo = {
            'status': True,
            'errLog': '',
            'content': ''
        }
        try:
            port = int(self.port)
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.ip, port, self.username, self.password, timeout=self.timeout,
                        banner_timeout=self.banner_timeout)
            njInfo['content'] = ssh
        except Exception as e:
            njInfo['status'] = False
            njInfo['errLog'] = str(e)
        return njInfo

    def login(self):
        """Login method.
        Creates a login session for the program to send commands to the target device.
        """
        result = {
            'status': False,
            'errLog': ''
        }
        # sshv2(ip,username,password,timeout,port=22)
        sshChannel = self.sshv2()
        if sshChannel['status']:
            # Login succeed, init shell
            try:
                result['status'] = True
                self._channel = sshChannel['content']
                # resize virtual console window size to 10000*10000
                self.shell = self._channel.invoke_shell(width=10000, height=10000)
                self.channel = self.shell
                tmpBuffer = ''
                while (
                        not re.search(self.basePrompt, tmpBuffer.split('\n')[-1])
                ) and (
                        not re.search('new +password', tmpBuffer.split('\n')[-1], flags=re.IGNORECASE)
                ) and (
                        not re.search('the password needs to be changed\. change now\? \[Y/N\]:$',
                                      tmpBuffer.split('\n')[-1], flags=re.IGNORECASE)
                ):
                    tmpBuffer += self.shell.recv(1024).decode()
                # if prompt is 'New Password' ,raise Error.
                if re.search('new +password', tmpBuffer.split('\n')[-1], flags=re.IGNORECASE):
                    raise Exception(
                        '[Login Error]: %s: Password expired, needed to be updated!' % self.ip
                    )
                if re.search('the password needs to be changed\. change now\? \[Y/N\]:$', tmpBuffer.split('\n')[-1],
                             flags=re.IGNORECASE):
                    self.shell.sendall("N" + "\r\n")

                self.shell.settimeout(self.timeout)
                # Record login status to True.
                self.isLogin = True
                self.getPrompt()
            except Exception as e:
                result['status'] = False
                result['errLog'] = str(e)
        else:
            # Login failed
            self.isLogin = False
            result['errLog'] = sshChannel['errLog']
        return result

    def logout(self):
        """Logout method
        A session used to log out of a target device
        """
        result = {
            'status': False,
            'errLog': ''
        }
        try:
            # Close SSH
            self._channel.close()
            # Modify login status to False.
            self.isLogin = False
            result['status'] = True
        except Exception as e:
            result['status'] = False
            result['errLog'] = str(e)
        return result

    def execute(self, cmd):
        """execute a command line, only suitable for the scene when
        the prompt is equal before and after execution
        """
        result = {
            'status': True,
            'content': '',
            'errLog': ''
        }
        self.cleanBuffer()
        if self.isLogin:
            # check login status
            # [ex] when send('ls\r'),get 'ls\r\nroot base etc \r\n[wangzhe@cloudlab100 ~]$ '
            # [ex] data should be 'root base etc '
            self.shell.send(cmd + "\r")
            resultPattern = re.compile('[\r\n]+([\s\S]*)[\r\n]+(\x1b\[m)?' + self.prompt)
            try:
                while not re.search(self.prompt, result['content'].split('\n')[-1]):
                    self.getMore(result['content'])
                    result['content'] += self.shell.recv(1024).decode()
                # try to extract the return data
                tmp = re.search(resultPattern, result['content']).group(1)
                # Delete special characters caused by More split screen.
                tmp = re.sub("<--- More --->\\r +\\r", "", tmp)
                tmp = re.sub(" *---- More ----\x1b\[42D                                          \x1b\[42D", "", tmp)
                # remove the More charactor
                tmp = re.sub(' \-\-More\(CTRL\+C break\)\-\- (\x00|\x08){0,} +(\x00|\x08){0,}', "", tmp)
                tmp = re.sub("---- More ----.*\[16D.*\[16D", "", tmp)
                tmp = re.sub(r"---MORE---", "", tmp)
                # remove the space key
                tmp = re.sub("(\x08)+ +", "", tmp)
                result['content'] = tmp
            except Exception as e:
                # pattern not match
                result['status'] = False
                result['content'] = result['content']
                result['errLog'] = str(e)
        else:
            # not login
            result['status'] = False
            result['errLog'] = '[Execute Error]: device not login'
        return result

    def command(self, cmd=None, prompt=None, timeout=30):
        """execute a command line, powerful and suitable for any scene,
        but need to define whole prompt dict list
        """
        # regx compile
        _promptKey = prompt.keys()
        for key in _promptKey:
            prompt[key] = re.compile(prompt[key])
        result = {
            'status': False,
            'content': '',
            'errLog': '',
            "state": None
        }
        if self.isLogin is False:
            result['errLog'] = '[Execute Error]: device not login.'
            return result
        # Setting timeout.
        # self.shell.settimeout(timeout)
        # Parameters check
        parameterFormat = {
            "success": "regular-expression-success",
            "error": "regular-expression-error"
        }
        if (cmd is None) or (not isinstance(prompt, dict)) or (not isinstance(timeout, int)):
            raise Exception("You should given a parameter for prompt such as: %s" % (str(parameterFormat)))
        # Clean buffer data.
        self.cleanBuffer()
        try:
            # send a command
            # self.shell.send("{cmd}\r".format(cmd=cmd))
            self.shell.sendall(cmd + "\r\n")
        except Exception:
            # break, if faild
            result["errLog"] = "Forward has sent a command failure."
            return result
        isBreak = False
        while True:
            # Remove special characters.
            result["content"] = re.sub("", "", result["content"])
            self.getMore(result["content"])
            try:
                result["content"] += self.shell.recv(204800).decode(errors="ignore")
            except Exception as e:
                result["errLog"] = "Forward had recived data timeout. [%s]" % str(e)
                return result
            # Mathing specify key
            for key in prompt:
                if re.search(prompt[key], result["content"]):
                    # Found it
                    result["state"] = key
                    isBreak = True
                    break
            # Keywords have been captured.
            if isBreak is True:
                break
        # Clearing special characters
        result["content"] = re.sub(" *---- More ----\x1b\[42D                                          \x1b\[42D",
                                   "", result["content"])
        result["content"] = re.sub("<--- More --->\\r +\\r", "", result["content"])
        # remove the More charactor
        result["content"] = re.sub(' \-\-More\(CTRL\+C break\)\-\- (\x00|\x08){0,} +(\x00|\x08){0,}', "",
                                   result["content"])
        result["content"] = re.sub("----.*More.*----.*\[16D.*\[16D", "", result["content"])
        result["content"] = re.sub(r"---MORE---", "", result["content"])
        # remove the space key
        result["content"] = re.sub("(\x08)+ +", "", result["content"])
        result["status"] = True
        return result

    def getPrompt(self):
        """Automatically get the current system prompt by sending a carriage return
        """
        if self.isLogin:
            # login status True
            result = ''
            self.cleanBuffer()
            self.shell.send('\n')
            # set recv timeout to self.timeout/10 fot temporary
            while not re.search(self.basePrompt, result):
                result += self.shell.recv(1024).decode()
            if result:
                # recv() get something
                # select last line character,[ex]' >[localhost@labstill019~]$ '
                self.prompt = result.split('\n')[-1]
                # [ex]'>[localhost@labstill019~]$'
                # self.prompt=self.prompt.split()[0]
                # [ex]'[localhost@labstill019~]'
                # self.prompt=self.prompt[1:-1]
                # [ex]'\\[localhost\\@labstill019\\~\\]$'
                if re.search("> ?$", self.prompt):
                    # If last character of host prompt of the device ens in '>',
                    # the command line of device in gneral mode.
                    self.mode = 1
                elif re.search("(#|\]) ?$", self.prompt):
                    # If last character of host prompt of the device ens in '#',
                    # the command line of device in enable mode.
                    self.mode = 2
                self.prompt = re.escape(self.prompt)
                return self.prompt
            else:
                # timeout,get nothing,raise error
                raise Exception('[Get Prompt Error]: %s: Timeout,can not get prompt.' % self.ip)
        else:
            # login status failed
            raise Exception('[Get Prompt Error]: %s: Not login yet.' % self.ip)

    def getMore(self, bufferData):
        """Automatically get more echo infos by sending a blank symbol
        """
        # if check buffer data has 'more' flag, at last line.
        if re.search(self.moreFlag, bufferData.split('\n')[-1]):
            # can't used to \n and ' \r' ,because product enter character
            self.shell.send(' ')
        # self.shell.send(' ')

    def cleanBuffer(self):
        """Clean the shell buffer whatever they are, by sending a carriage return
        """
        if self.shell.recv_ready():
            self.shell.recv(4096).decode()
        self.shell.send('\n')
        buff = ''
        # When after switching mode, the prompt will change, it should be based on basePrompt to check and at last line
        while not re.search(self.basePrompt, buff.split('\n')[-1]):
            try:
                self.getMore(buff)
                buff += self.shell.recv(1024).decode()
            except Exception:
                raise Exception('[Clean Buffer Error]: %s: Receive timeout [%s]' % (self.ip, buff))


def transform_subnet_mask(netmask):
    # Converts the subnet mask to bits
    result = ""
    for num in netmask.split('.'):
        temp = str(bin(int(num)))[2:]
        result += temp
    return str(len("".join(str(result).split('0')[0:1])))


def command(devip, type, username, passwd, cmd):
    # fw = Forward()
    # ipArr = [devip]
    # fw.addTargets(ipArr, type, username, passwd)
    # instances = fw.getInstances()
    # ins = instances[devip]
    ins = BASESSHV2(devip, username, passwd)
    if "|" in cmd:
        success = "\|".join(cmd.split("|")) + '[\S\s]+(#|>|\]) *$'
    else:
        success = cmd + '[\S\s]+(#|>|\]) *$'
    promat = dict(success=success, error="Unrecognized command[\s\S]+")
    ret = ins.command(cmd, promat)
    return ret


class ObjectThread(threading.Thread):
    def __init__(self, threadID, ips, type, username, passwd, cmd, promat):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.ips = ips
        self.type = type
        self.username = username
        self.passwd = passwd
        self.cmd = cmd
        self.promat = promat

    def run(self):
        self.result = collect_data(self.ips, self.type, self.username, self.passwd, self.cmd, self.promat)

    def get_result(self):
        try:
            return self.result
        except Exception:
            return None


# # 调用工具执行接口
# def tools_execution(file_name, content):
#     operation_url = '/tools/execution'
#     url = 'http://{0}{1}'.format("10.242.130.147", operation_url)
#     data = {
#         "toolId": "35dfe9998387a1f8885713acf66e07b9",
#         "inputs": {
#             "@agents": [{
#                 "ip": "192.168.242.10",
#                 "instanceId": "595b2a45e26df"
#             }],
#             "file_name": file_name,
#             "content": content
#         },
#         "instanceMap": {},
#         "execUser": "root",
#         "windowsExecUser": "System",
#         "batchStrategy": {
#             "enabled": False
#         }
#     }
#     # cmdb_request(method='post', url=url, data=data)


# # 发起接口请求
# def cmdb_request(url, data, method='POST'):
#     url = urllib.quote(url, safe='/:?=&')
#     headers = {
#         'content-type': 'application/json',
#         'user': EASYOPS_USER,
#         'org': str(EASYOPS_ORG),
#         'host': 'tool.easyops-only.com',
#         'Connection': 'close'
#     }
#
#     # print u'---------- 发送 cmdb 请求: %s %s ' % (method, url)
#     try:
#         r = requests.request(method=method, url=url, headers=headers, json=data)
#
#         if r.status_code == 200:
#             # print u'---------- cmdb 请求成功!'f
#             jsn = r.json()
#         else:
#             print(u'---------- 请求失败!错误码为:status_code = %s' % r.status_code)
#             print(u'---------- 失败详情为: error_info = %s' % r.text)
#             return None
#
#         if int(jsn['code']) == 0:
#             # print u'---------- 操作进行成功!\n'
#             return jsn
#         else:
#             print(u'---------- 操作失败: ' + jsn['error'] + ' -- ')
#             return None
#
#     except Exception as e:
#         print(e)
#         return None


def collect_data(ips, _type, username, passwd, cmd, promat):
    ips = ips[:]

    # 原实现方式用Forward()，已经注释
    # def forward_run(queue, ip, _type, username, passwd, cmd, promat):
    #     try:
    #         fw = Forward()
    #         fw.addTargets([ip], _type, username, passwd)
    #         instances = fw.getInstances()
    #         ins = instances[ip]
    #
    #         prompt = dict(success=promat, error="Unrecognized command[\s\S]+")
    #         # print("================================" + str(prompt))
    #         tmp = ins.command(cmd=cmd, prompt=prompt)
    #         ip_result = {"ip": ip, "tmp": tmp['content']}
    #         # print("*******************************" + str(queue.qsize()))
    #         queue.put(ip_result)
    #         # print("*******************************" + str(queue.qsize()))
    #     except Exception as e:
    #         print("异常设备：" + str(ip) + ", 异常信息：" + str(e))
    #         print(">>>>>>>{}".format(traceback.format_exc()))

    def forward_run(queue, ip, _type, username, passwd, cmd, promat):
        ins = BASESSHV2(ip, username, passwd)
        if not ins.isLogin:
            print("timeout {}".format(ip))
            ins.logout()
            exit(0)
        tmp = ins.execute(cmd=cmd)
        ip_result = {"ip": ip, "tmp": tmp['content']}
        queue.put(ip_result)
        ins.logout()

    result = []
    try:
        manager = Manager()
        queue = manager.Queue()
        m = 0

        while len(ips) > 0:

            proc_list = []
            for i in range(50):
                if len(ips) > 0:
                    ip = ips.pop(0)
                    proc = Process(target=forward_run, args=(queue, ip, _type, username, passwd, cmd, promat))
                    proc.start()
                    proc_list.append(proc)
            while len(proc_list) > 0:
                temp = []
                for i in range(len(proc_list)):
                    proc = proc_list.pop(0)
                    if not proc.is_alive():
                        # print("================" + str(proc))
                        proc.join()
                    else:
                        temp.append(proc)
                if temp:
                    proc_list.extend(temp)
                    time.sleep(2)

            while not queue.empty():
                ret = queue.get()
                m = m + 1
                result.append(ret)
    # print("MMMMMMMMMMMMMMMMMMMM" + str(m))
    except Exception as e:
        print(">>>>>>>5555{}".format(traceback.format_exc()))
    return result


def write_file(data, file_name):
    with open(file_name, 'w') as f:
        f.write(data)


def internal(ipadd):
    a = re.findall(
        r'^((192\.168)|(10\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d))|(172\.(1[6-9]|2[0-9]|3[0-1])))\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$',
        ipadd)
    if a:
        return True


def get_public_ip(pool, type_ip):
    """
    :param pool: 机房标识401、402、501
    :param type_ip: vlan/vrf/port_vlan
    :return:
    """

    def formate_public_ip_cmnet_ne40e_x16a(ipv4_inters, ipv6_inters, inter_brief):
        ip_result = []
        inter_result = []
        result = []
        for device1 in ipv4_inters:
            start = False
            for line in device1['tmp'].split('\r\n'):
                # "Interface                         IP Address/Mask      Physical   Protocol VPN"
                tmp = re.search(r'Interface\s*IP Address/Mask\s*Physical\s*Protocol\s*VPN', line)
                if tmp:
                    start = True
                    continue
                if not start:
                    continue
                # 100GE2/0/1                        unassigned           *down      down     --
                # Eth-Trunk1                        192.168.252.21/30    up         up       --
                tmp1 = re.search(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+', line)
                if tmp1 and tmp1.group(2) != 'unassigned':
                    interface = tmp1.group(1)
                    # interface   ip_addr  type
                    line_info1 = [device1["ip"], interface, tmp1.group(2).split('/')[0], "ipv4"]
                    ip_result.append(line_info1)
        # print("ip result v4: {}".format(ip_result))
        for device2 in ipv6_inters:
            for line1 in re.split(r'\r\n(?=.*?\r\n\[IPv6 Address\])', device2['tmp']):
                tmp2 = re.search(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\[IPv6 Address\](.*)', line1)
                if tmp2 and "unassigned" not in tmp2.group(5):
                    interface = tmp2.group(1)
                    # interface   ip_addr  type
                    line_info2 = [device2["ip"], interface, tmp2.group(5).strip(), "ipv6"]
                    ip_result.append(line_info2)
        # print("ip result v6: {}".format(ip_result))
        for device3 in inter_brief:
            isBreak = False
            for line3 in device3['tmp'].split("\r\n"):
                if re.search(r'Interface\s+PHY\s+Protocol\s+Description', line3):
                    isBreak = True
                    continue
                if not isBreak:
                    continue
                tmp3 = re.search(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+|\s+)', line3)
                if tmp3:
                    inter = tmp3.group(1)
                    # device_ip  interface   descr
                    line_info3 = [device3["ip"], inter, tmp3.group(4)]
                    inter_result.append(line_info3)
        # print("inter_result: {}".format(ip_result))
        for ip in ip_result:
            if "loopback" in ip[1].lower():
                temp = ip[:]
                temp.append("loopback")
                temp1 = "@#$".join(temp)
                result.append(temp1)
                continue
            for inter in inter_result:
                if ip[0] == inter[0] and "-BR" in inter[2] and ip[1] == inter[1]:
                    temp = ip[:]
                    temp.append("省干")
                    temp1 = "@#$".join(temp)
                    result.append(temp1)
                if ip[0] == inter[0] and "-BB-" in inter[2] and ip[1] == inter[1]:
                    temp = ip[:]
                    temp.append("国干")
                    temp1 = "@#$".join(temp)
                    result.append(temp1)
        # print("result: {}".format(ip_result))
        return result

    def formate_public_ip_cmnet_m6000_8s(ipv4_inters, ipv6_inters, inter_brief):
        ip_result = []
        inter_result = []
        result = []
        for device1 in ipv4_inters:
            isBreak = True
            for line in device1["tmp"].split("\r\n"):
                try:
                    # Interface                       IP-Address      Mask            Admin Phy  Prot
                    # cgei-0/2/0/1                    221.183.63.234  255.255.255.252 up    up   up
                    temp = re.search(r'Interface\s+IP-Address', line)
                    if temp:
                        isBreak = False
                        continue
                    if isBreak:
                        continue
                    tmp = re.search(r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
                    if tmp and tmp.group(2) != "unassigned":
                        interface = tmp.group(1)
                        # interface   ip_addr  type
                        line_info = [device1["ip"], interface, tmp.group(2), "ipv4"]
                        ip_result.append(line_info)
                except Exception as e:
                    continue
        for device2 in ipv6_inters:
            for line1 in re.split(r'\r\n(?=.*?\[\S+\])', device2["tmp"]):
                try:
                    tmp = re.search(r'(\S+)\s+\[([a-z]+)/([a-z]+)\]\s+([\S\s]+)', line1)
                    if tmp:
                        if "unassigned" in tmp.group(4):
                            continue
                        if "#" in tmp.group(4):
                            ip_addr = ", ".join([t for t in tmp.group(4).split('\r\n') if "#" not in t]).replace(" ",
                                                                                                                 "")
                        else:
                            ip_addr = tmp.group(4).strip().replace(" ", "").replace("\r\n", ", ")
                        interface = tmp.group(1)
                        # interface   ip_addr  type
                        line_info = [device1["ip"], interface, ip_addr.split(",")[-1].split("/")[0], "ipv6"]
                        ip_result.append(line_info)
                except Exception as e:
                    continue
        for device3 in inter_brief:
            try:
                isBreak = True
                for line3 in re.split(r'\r\n', device3["tmp"]):
                    # Interface                       AdminStatus  PhyStatus  Protocol  Description
                    # xgei-0/0/0/1                    up           up         up        TO-NFV-D-HNGZ-00A-2501-AD08-S-DDOS-01-tengige1_0-10G
                    temp = re.search(r'Interface\s+AdminStatus', line3)
                    if temp:
                        isBreak = False
                        continue
                    if isBreak:
                        continue
                    tmp3 = re.search(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line3)
                    if tmp3:
                        inter = tmp3.group(1)
                        # device_ip  interface   descr
                        line_info3 = [device3["ip"], inter, tmp3.group(5)]
                        inter_result.append(line_info3)
            except Exception as e:
                continue
        for ip in ip_result:
            try:
                if "loopback" in ip[1].lower():
                    temp = ip[:]
                    temp.append("loopback")
                    temp1 = "@#$".join(temp)
                    result.append(temp1)
                    continue
                for inter in inter_result:
                    try:
                        if ip[0] == inter[0] and "-BR" in inter[2] and ip[1] == inter[1]:
                            temp = ip[:]
                            temp.append("省干")
                            temp1 = "@#$".join(temp)
                            result.append(temp1)
                        if ip[0] == inter[0] and "-BB-" in inter[2] and ip[1] == inter[1]:
                            temp = ip[:]
                            temp.append("国干")
                            temp1 = "@#$".join(temp)
                            result.append(temp1)
                    except Exception as e:
                        continue
            except Exception as e:
                continue
        return result

    def formate_public_ip_cmnet_m6000_18s(ipv4_inters, ipv6_inters, inter_brief):
        result = formate_public_ip_cmnet_m6000_8s(ipv4_inters, ipv6_inters, inter_brief)
        return result

    def formate_public_ip_fw_e8000e(nat_data):
        result = []
        temp = []
        for device1 in nat_data:
            for line in re.split(r'\r\n', device1["tmp"]):
                # nat server HNGZqgNEFP1AHY-00AHW011_01_NAT_Server protocol tcp global 39.138.5.1 www inside 192.168.254.226 www no-reverse
                tmp = re.search(r'nat server (\S+) protocol.*?global (\S+).*?inside (\S+)', line)
                if tmp and tmp.group(2) not in temp:
                    temp.append(tmp.group(2))
                    # device_ip  interface   ip_addr  type  purpose
                    line_info = [device1["ip"], "", tmp.group(2), "ipv4", tmp.group(1)]
                    result.append("@#$".join(line_info))
        return result

    def formate_public_ip_e_rt_m6000_8s(intf_data):
        result = []
        for device1 in intf_data:
            try:
                for line in re.split(r'\$', device1["tmp"]):
                    print(line)
                    try:
                        """interface loopback12
                          description For OSPF_156_OSPFv3_156
                          ip vrf forwarding ChinaMobile_CXINAN
                          ip address 10.36.97.108 255.255.255.255
                          ipv6 enable
                          ipv6 address 2409:805b:600e:a00::fffa/128"""
                        tmp = re.search(r'interface (\S+)[\S\s]+description (.*)[\S\s]+ip vrf forwarding (\S+)', line)
                        if tmp and re.search(r'NFV_CMNet', tmp.group(3), re.I):
                            tmp1 = re.search(r'ip address ([0-9.]+) ([0-9.]+)', line)
                            if tmp1 and not internal(tmp1.group(1)):
                                # device_ip  interface   ip_addr  type  purpose
                                line_info = [device1["ip"], tmp.group(1), tmp1.group(1), "ipv4", tmp.group(2)]
                                result.append("@#$".join(line_info))
                            tmp2 = re.search(r'ipv6 address (\S+)/', line)
                            if tmp2 and not re.match(r'2409:8086:861', tmp2.group(1)):
                                line_info = [device1["ip"], tmp.group(1), tmp2.group(1), "ipv6", tmp.group(2)]
                                result.append("@#$".join(line_info))
                    except Exception as e:
                        continue
            except Exception as e:
                print(e)
        return result

    def formate_public_ip_e_rt_m6000_18s(intf_data):
        result = formate_public_ip_e_rt_m6000_8s(intf_data)
        return result

    def formate_public_ip_e_rt_ne40e_x16a(intf_data):
        result = []
        for device1 in intf_data:
            for line in re.split(r'#', device1["tmp"]):
                """interface LoopBack115
                   description Loopback For OSPF_115-OSPv3_715
                   ip binding vpn-instance ChinaMobile_IMS_SG
                   ipv6 enable
                   ip address 10.192.247.12 255.255.255.255
                   ipv6 address 2409:8054:5005:1501::FFFA/128
                   ospfv3 715 area 0.0.0.0"""
                tmp = re.search(r'interface (\S+)[\S\s]+description (.*)[\S\s]+ip binding vpn-instance (\S+)', line)
                if tmp and re.search(r'NFV_CMNet', tmp.group(3), re.I):
                    tmp1 = re.search(r'ip address ([0-9.]+) ([0-9.]+)', line)
                    if tmp1 and not internal(tmp1.group(1)):
                        # device_ip  interface   ip_addr  type  purpose
                        line_info = [device1["ip"], tmp.group(1), tmp1.group(1), "ipv4", tmp.group(2)]
                        result.append("@#$".join(line_info))
                    tmp2 = re.search(r'ipv6 address (\S+)/', line)
                    if tmp2 and not re.match(r'2409:8086:861', tmp2.group(1)):
                        line_info = [device1["ip"], tmp.group(1), tmp2.group(1), "ipv6", tmp.group(2)]
                        result.append("@#$".join(line_info))
        return result

    def formate_public_ip_zx_9908(ipv4_inters, ipv6_inters, inter_brief):
        result = formate_public_ip_cmnet_m6000_8s(ipv4_inters, ipv6_inters, inter_brief)
        return result

    def formate_public_ip_zx_5960_72DL_H(ipv4_inters, ipv6_inters, inter_brief):
        result = formate_public_ip_cmnet_m6000_8s(ipv4_inters, ipv6_inters, inter_brief)
        return result

    vrf_filename = 'DEVICE_PUBLIC_IP' + '_' + pool + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'
    content = ["device_ip@#$interface@#$ip_addr@#$type@#$purpose"]

    cmd = {
        "cmnet_ne40e_x16a": ["display ip interface brief", "display ipv6 interface brief", "display interface des",
                             "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],  # Huawei
        "cmnet_m6000_8s": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                           "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],  # ZTE
        "cmnet_m6000_18s": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                            "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],  # ZTE
        "fw_e8000e": ["display current-configuration | include nat server", "nat server[\S\s]+(#|>|\]) *$"],  # Huawei
        "e_rt_m6000_8s": ["show running-config if-intf", "if-intf[\S\s]+(#|>|\]) *$"],  # ZTE
        "e_rt_m6000_18s": ["show running-config if-intf", "if-intf[\S\s]+(#|>|\]) *$"],  # ZTE
        "e_rt_ne40e_x16a": ["display current-configuration interface", "interface[\S\s]+(#|>|\]) *$"],  # Huawei

        # peach添加交换机
        "zx_9908": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                    "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],

        "zx_5960_72DL_H": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                           "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],
    }

    for _type in type_ip:
        if _type not in cmd:
            print("采集中无型号为{}的设备".format(_type))
            continue
        device_name = DEVICE_NAME
        device_password = DEVICE_PASSWORD
        if _type in ["cmnet_ne40e_x16a", "cmnet_m6000_8s", "cmnet_m6000_18s", "zx_9908", "zx_5960_72DL_H"]:
            type = _type.split("cmnet_")[-1]
            ipv4_inters = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][0],
                                       cmd[_type][3])
            ipv6_inters = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][1],
                                       cmd[_type][3])
            inter_brief = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][2],
                                       cmd[_type][4])
            formate_list = eval("formate_public_ip_" + _type)(ipv4_inters, ipv6_inters, inter_brief)

        elif _type == "fw_e8000e":
            type = _type.split("fw_")[-1]
            nat_data = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][0],
                                    cmd[_type][1])
            formate_list = eval("formate_public_ip_" + _type)(nat_data)

        elif _type in ["e_rt_ne40e_x16a", "e_rt_m6000_8s", "e_rt_m6000_18s"]:
            type = _type.split("e_rt_")[-1]
            intf_data = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][0],
                                     cmd[_type][1])
            formate_list = eval("formate_public_ip_" + _type)(intf_data)

        content.extend(formate_list)

    # tools_execution(vrf_filename, "\n".join(content))  # 执行工具将文件保存到指定设备
    write_file("\n".join(content), vrf_filename)


def get_public_subnet(pool, type_ip):
    def formate_public_subnet_cmnet_ne40e_x16a(data):
        result = []
        # ip route-static 223.103.141.0 255.255.255.0 NULL0 track bfd-session v4_CE_EPCFW description Summay-[NFV-D-HNGZ-02A-2401-AD17-S-FW-01]-[GuangXi_vEPC]
        # ipv6 route-static 2409:8057:3802:: 48 NULL0 track bfd-session v6_CE_EPCFW description Summay-[NFV-D-HNGZ-02A-2401-AD17-S-FW-01]-[YeWuHuiZong]
        for device1 in data:
            for line in re.split(r'\r\n', device1["tmp"]):
                tmp = re.search(r'ip route-static (\S+)\s+(\S+)(.*)', line)
                if tmp:
                    ip = tmp.group(1) + "/" + transform_subnet_mask(tmp.group(2))
                    line_info = [device1["ip"], ip, tmp.group(3), pool_alias[pool]]
                    result.append("@#$".join(line_info))
                    continue
                tmp1 = re.search(r'ipv6 route-static (\S+)\s+(\S+)(.*)', line)
                if tmp1:
                    # device_ip@#$ip_addr@#$descr
                    ip = tmp1.group(1) + "/" + tmp1.group(2)
                    line_info = [device1["ip"], ip, tmp1.group(3), pool_alias[pool]]
                    result.append("@#$".join(line_info))
        return result

    def formate_public_subnet_cmnet_m6000_8s(data):
        result = []
        # ipv6 route 2409:8080:802:5000::/52 null1 track v6_CE_EPCFW name Summay-[NFV-D-HNGZ-00A-2501-AD09-S-FW-01]-[NEFP]
        # ip route 120.196.209.0 255.255.255.0 null1 track v4_CE_EPCFW name Summay-[NFV-D-HNGZ-00A-2501-AE09-S-FW-02]-[HW5GMC]
        # ipv6 route 2409:805b:2903::/48 null1 track To_FW_v6
        # ip route 223.103.149.0 255.255.255.0 null1 track To_FW_v4
        for device1 in data:
            for line in re.split(r'\r\n', device1["tmp"]):
                tmp = re.search(r'ip route (\S+)\s+(\S+)(.*)', line)
                if tmp:
                    ip = tmp.group(1) + "/" + transform_subnet_mask(tmp.group(2))
                    line_info = [device1["ip"], ip, tmp.group(3), pool_alias[pool]]
                    result.append("@#$".join(line_info))
                    continue
                tmp1 = re.search(r'ipv6 route (\S+)(.*)', line)
                if tmp1:
                    # device_ip@#$ip_addr@#$descr
                    ip = tmp1.group(1)
                    line_info = [device1["ip"], ip, tmp1.group(2), pool_alias[pool]]
                    result.append("@#$".join(line_info))
        return result

    def formate_public_subnet_cmnet_m6000_18s(data):
        result = formate_public_subnet_cmnet_m6000_8s(data)
        return result

    vrf_filename = 'DEVICE_PUBLIC_SUBNET' + '_' + pool + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'
    content = ["device_ip@#$ip_addr@#$descr@#$pool"]

    cmd = {
        "cmnet_ne40e_x16a": ["display current-config | include NULL0", "include NULL0[\S\s]+(#|>|\]) *$"],  # Huawei
        "cmnet_m6000_8s": ["show running-config | include null1", "include null1[\S\s]+(#|>|\]) *$"],  # ZTE
        "cmnet_m6000_18s": ["show running-config | include null1", "include null1[\S\s]+(#|>|\]) *$"],  # ZTE
    }

    for _type in type_ip:
        if _type not in cmd:
            print("采集中无型号为{}的设备".format(_type))
            continue
        device_name = DEVICE_NAME
        device_password = DEVICE_PASSWORD
        if _type in ["cmnet_ne40e_x16a", "cmnet_m6000_8s", "cmnet_m6000_18s"]:
            type = _type.split("cmnet_")[-1]
            data = collect_data(type_ip[_type], type, device_name, device_password, cmd[_type][0],
                                cmd[_type][1])
            formate_list = eval("formate_public_subnet_" + _type)(data)
        content.extend(formate_list)
    # tools_execution(vrf_filename, "\n".join(content))  # 执行工具将文件保存到指定设备
    write_file("\n".join(content), vrf_filename)


def main():
    # type_ip     # {"型号":["设备IP1","设备IP2"]}
    # pool      # 机房标识401、402、501
    # source        # vlan/vrf/port_vlan

    # type_ip = """{"e_rt_ne40e_x16a": ["2409:8086:8612:80:0:0:0:e", "2409:8086:8612:80:0:0:0:d"],
    # "cmnet_ne40e_x16a": ["2409:8086:8612:80:0:0:0:f", "2409:8086:8612:80:0:0:0:10"],
    # "fw_e8000e": ["2409:8086:8612:80:0:0:0:11", "2409:8086:8612:80:0:0:0:12"]}"""
    type_ip = """{
        "zx_9908": ['2409:8086:8514:80:0:0:0:1', '2409:8086:8514:80:0:0:0:2', '2409:8086:8514:80:0:0:0:3', '2409:8086:8514:80:0:0:0:4', '2409:8086:8514:80:0:0:0:5', '2409:8086:8514:80:0:0:0:6'],

            }"""

    # "zx_5960_72DL_H": ['2409:8086:8514:80:0:0:0:10', '2409:8086:8514:80:0:0:0:11', '2409:8086:8514:80:0:0:0:12', '2409:8086:8514:80:0:0:0:13', '2409:8086:8514:80:0:0:0:14', '2409:8086:8514:80:0:0:0:15', '2409:8086:8514:80:0:0:0:16', '2409:8086:8514:80:0:0:0:17', '2409:8086:8514:80:0:0:0:18', '2409:8086:8514:80:0:0:0:19', '2409:8086:8514:80:0:0:0:1a', '2409:8086:8514:80:0:0:0:1b', '2409:8086:8514:80:0:0:0:1c', '2409:8086:8514:80:0:0:0:1d', '2409:8086:8514:80:0:0:0:1e', '2409:8086:8514:80:0:0:0:1f', '2409:8086:8514:80:0:0:0:20', '2409:8086:8514:80:0:0:0:21', '2409:8086:8514:80:0:0:0:22', '2409:8086:8514:80:0:0:0:23', '2409:8086:8514:80:0:0:0:24', '2409:8086:8514:80:0:0:0:25', '2409:8086:8514:80:0:0:0:26', '2409:8086:8514:80:0:0:0:27', '2409:8086:8514:80:0:0:0:28', '2409:8086:8514:80:0:0:0:29', '2409:8086:8514:80:0:0:0:2a', '2409:8086:8514:80:0:0:0:2b', '2409:8086:8514:80:0:0:0:2c', '2409:8086:8514:80:0:0:0:2d', '2409:8086:8514:80:0:0:0:2e', '2409:8086:8514:80:0:0:0:2f', '2409:8086:8514:80:0:0:0:30', '2409:8086:8514:80:0:0:0:31', '2409:8086:8514:80:0:0:0:32', '2409:8086:8514:80:0:0:0:33', '2409:8086:8514:80:0:0:0:34', '2409:8086:8514:80:0:0:0:35', '2409:8086:8514:80:0:0:0:36', '2409:8086:8514:80:0:0:0:37', '2409:8086:8514:80:0:0:0:38', '2409:8086:8514:80:0:0:0:39', '2409:8086:8514:80:0:0:0:3a', '2409:8086:8514:80:0:0:0:3b', '2409:8086:8514:80:0:0:0:3c', '2409:8086:8514:80:0:0:0:3d', '2409:8086:8514:80:0:0:0:3e', '2409:8086:8514:80:0:0:0:3f', '2409:8086:8514:80:0:0:0:40', '2409:8086:8514:80:0:0:0:41', '2409:8086:8514:80:0:0:0:42', '2409:8086:8514:80:0:0:0:43', '2409:8086:8514:80:0:0:0:44', '2409:8086:8514:80:0:0:0:45', '2409:8086:8514:80:0:0:0:46', '2409:8086:8514:80:0:0:0:47', '2409:8086:8514:80:0:0:0:48', '2409:8086:8514:80:0:0:0:49', '2409:8086:8514:80:0:0:0:4a', '2409:8086:8514:80:0:0:0:4b', '2409:8086:8514:80:0:0:0:4c', '2409:8086:8514:80:0:0:0:4d', '2409:8086:8514:80:0:0:0:4e', '2409:8086:8514:80:0:0:0:4f', '2409:8086:8514:80:0:0:0:50', '2409:8086:8514:80:0:0:0:51', '2409:8086:8514:80:0:0:0:52', '2409:8086:8514:80:0:0:0:53', '2409:8086:8514:80:0:0:0:54', '2409:8086:8514:80:0:0:0:55', '2409:8086:8514:80:0:0:0:56', '2409:8086:8514:80:0:0:0:57', '2409:8086:8514:80:0:0:0:58', '2409:8086:8514:80:0:0:0:59', '2409:8086:8514:80:0:0:0:5a', '2409:8086:8514:80:0:0:0:5b', '2409:8086:8514:80:0:0:0:5c', '2409:8086:8514:80:0:0:0:5d', '2409:8086:8514:80:0:0:0:5e', '2409:8086:8514:80:0:0:0:5f', '2409:8086:8514:80:0:0:0:60', '2409:8086:8514:80:0:0:0:61', '2409:8086:8514:80:0:0:0:62', '2409:8086:8514:80:0:0:0:63', '2409:8086:8514:80:0:0:0:64', '2409:8086:8514:80:0:0:0:65', '2409:8086:8514:80:0:0:0:66', '2409:8086:8514:80:0:0:0:67', '2409:8086:8514:80:0:0:0:68', '2409:8086:8514:80:0:0:0:69', '2409:8086:8514:80:0:0:0:6a', '2409:8086:8514:80:0:0:0:6b', '2409:8086:8514:80:0:0:0:6c', '2409:8086:8514:80:0:0:0:6d', '2409:8086:8514:80:0:0:0:6e', '2409:8086:8514:80:0:0:0:6f', '2409:8086:8514:80:0:0:0:70', '2409:8086:8514:80:0:0:0:71', '2409:8086:8514:80:0:0:0:72', '2409:8086:8514:80:0:0:0:73', '2409:8086:8514:80:0:0:0:74', '2409:8086:8514:80:0:0:0:75', '2409:8086:8514:80:0:0:0:76', '2409:8086:8514:80:0:0:0:77', '2409:8086:8514:80:0:0:0:78', '2409:8086:8514:80:0:0:0:79', '2409:8086:8514:80:0:0:0:7a', '2409:8086:8514:80:0:0:0:7b', '2409:8086:8514:80:0:0:0:7c', '2409:8086:8514:80:0:0:0:7d', '2409:8086:8514:80:0:0:0:7e', '2409:8086:8514:80:0:0:0:7f', '2409:8086:8514:80:0:0:0:80', '2409:8086:8514:80:0:0:0:81', '2409:8086:8514:80:0:0:0:82', '2409:8086:8514:80:0:0:0:83', '2409:8086:8514:80:0:0:0:84', '2409:8086:8514:80:0:0:0:85', '2409:8086:8514:80:0:0:0:86', '2409:8086:8514:80:0:0:0:87', '2409:8086:8514:80:0:0:0:88', '2409:8086:8514:80:0:0:0:89', '2409:8086:8514:80:0:0:0:8a', '2409:8086:8514:80:0:0:0:8b', '2409:8086:8514:80:0:0:0:8c', '2409:8086:8514:80:0:0:0:8d', '2409:8086:8514:80:0:0:0:8e', '2409:8086:8514:80:0:0:0:8f', '2409:8086:8514:80:0:0:0:90', '2409:8086:8514:80:0:0:0:91', '2409:8086:8514:80:0:0:0:92', '2409:8086:8514:80:0:0:0:93', '2409:8086:8514:80:0:0:0:94', '2409:8086:8514:80:0:0:0:95', '2409:8086:8514:80:0:0:0:96', '2409:8086:8514:80:0:0:0:97', '2409:8086:8514:80:0:0:0:98', '2409:8086:8514:80:0:0:0:99', '2409:8086:8514:80:0:0:0:9a', '2409:8086:8514:80:0:0:0:9b', '2409:8086:8514:80:0:0:0:9c', '2409:8086:8514:80:0:0:0:f', '2409:8086:8514:80:0:0:0:cc', '2409:8086:8514:80:0:0:0:cf', '2409:8086:8514:80:0:0:0:cd', '2409:8086:8514:80:0:0:0:d0', '2409:8086:8514:80:0:0:0:ce', '2409:8086:8514:80:0:0:0:d1', '2409:8086:8514:80:0:0:0:d2', '2409:8086:8514:80:0:0:0:d5', '2409:8086:8514:80:0:0:0:d3', '2409:8086:8514:80:0:0:0:d6', '2409:8086:8514:80:0:0:0:d4', '2409:8086:8514:80:0:0:0:d7']
    pool = "401"
    source = "public_ip"

    print(pool + ">>" + type_ip)
    model_ip = ast.literal_eval(type_ip)
    eval("get_" + source)(pool, model_ip)


if __name__ == '__main__':
    main()
