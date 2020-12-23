# -*- coding: utf-8 -*-
import copy
import re
import datetime
import ipaddress
from multiprocessing import Queue, Process, Manager
import time
import paramiko
import json
import gzip
import io
import os
import sys, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

if sys.version_info.major == 2:
    reload(sys)
    sys.setdefaultencoding('utf8')


def write_to_gz(file_name, _data):
    file_name = "/tmp/data/" + file_name + ".gz"
    with gzip.open(file_name, "wb") as output:
        with io.TextIOWrapper(output, encoding="utf-8") as write_fd:
            if sys.version_info.major == 2:
                write_fd.write(_data.decode())
            else:
                write_fd.write(_data)


class BASESSHV2(object):
    def __init__(self, ip, username, password, **kwargs):
        """Init a sshv2-like class instance, accept port/timeout/privilegePw as extra parameters
        """
        self.ip = ip
        self.username = username
        self.password = password

        self.port = kwargs['port'] if 'port' in kwargs else 22
        self.timeout = kwargs['timeout'] if 'timeout' in kwargs else 30
        self.banner_timeout = kwargs['banner_timeout'] if 'banner_timeout' in kwargs else 60
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


def collect_data(ips, _type, username, passwd, cmd, promat):
    """
    :param ips: 要采集的所有ip， list
    :param _type: 信号
    :param username: 采集登陆账号
    :param passwd: 采集登陆密码
    :param cmd: 采集命令
    :param promat:正则表达式
    :return:
    """

    logging.info('collect_data params ips: %s, _type:%s, username:%s, passwd:%s, cmd:%s, promat:%s' % (
        ips, _type, username, passwd, cmd, promat))

    def forward_run(queue, ip, _type, username, passwd, cmd, promat):
        ins = BASESSHV2(ip, username, passwd)
        if not ins.isLogin:
            #print("timeout {}".format(ip))
            print("\033[0;31;40m\ttimeout {timeout_ip}\033[0m".format(timeout_ip=ip))
            ins.logout()
            exit(0)
        tmp = ins.execute(cmd=cmd)
        ip_result = {"ip": ip, "tmp": tmp['content']}
        queue.put(ip_result)
        ins.logout()

    result = []
    manager = Manager()
    queue = manager.Queue()
    while len(ips) > 0:
        proc_list = []
        for i in range(20):
            if len(ips) > 0:
                ip = ips.pop(0)
                logging.info('ip: %s start..collect, cmd:%s' % (ip, cmd))
                proc = Process(target=forward_run, args=(queue, ip, _type, username, passwd, cmd, promat))
                proc.start()
                proc_list.append(proc)
        while len(proc_list) > 0:
            for i in range(len(proc_list)):
                proc = proc_list.pop(0)
                proc.join()
        while not queue.empty():
            ret = queue.get()
            result.append(ret)
    return result


def write_file(data, file_name):
    with open(file_name, 'w') as f:
        f.write(data)


def transform_subnet_mask(netmask):
    # Converts the subnet mask to bits
    result = ""
    for num in netmask.split('.'):
        temp = str(bin(int(num)))[2:]
        result += temp
    return len("".join(str(result).split('0')[0:1]))


def get_vlan(type_ip):
    """
    :param type_ip: 采集的数据 型号：ip列表
    :return:
    """
    vlan_cmd = {
        # "ce16816"   不知道命令，
        # "ce6856_48s6q_hi" 不知道命令，
        # "ce6881_48s6cq" 不知道命令
        "ce12808": ["display current-configuration interface Vlanif", "interface Vlanif[\S\s]+(#|>|\]) *$"],
        "ce16808": ["display current-configuration interface Vlanif", "interface Vlanif[\S\s]+(#|>|\]) *$"],
        "ce6856": ["dis current-configuration interface Eth-Trunk", "interface Eth-Trunk[\S\s]+(#|>|\]) *$"],
        # "ce6881_48s6cq": ["dis current-configuration interface Eth-Trunk", "interface Eth-Trunk[\S\s]+(#|>|\]) *$"],
        # 华为交换机st-eor/m-eor
        "ne40e_x16a": ["dis current-configuration interface Eth-Trunk", "interface Vlanif[\S\s]+(#|>|\]) *$"],
        # 华为路由器
        "f_9908": ["show running-config if-intf | begin vlan", "begin vlan[\S\s]+(#|>|\]) *$"],  # 中兴
        "m6000_18s": ["show running-config if-intf | begin vlan", "begin vlan[\S\s]+(#|>|\]) *$"],  # 中兴
        "f_5960_72dl_h": ["show running-config | begin SVLAN", "!</PRJES>"],  # 中兴

        # peach 12-22添加
        # 迈普交换机
        "s4320_56tc": ["show vlan", '']
    }

    def formate_vlan_ce16808(org_data):
        return formate_vlan_ce12808(org_data)

    def formate_vlan_ce6881_48s6cq(org_data):
        return formate_vlan_ce6856(org_data)

    def formate_vlan_ce6856_48s6q_hi(org_data):
        return formate_vlan_ce12808(org_data)

    def formate_vlan_ce12808(org_data):
        res_list = []
        for ip_result in org_data:
            text = ip_result['tmp']
            for line in text.split('#\r\n'):
                tmp = re.search('interface Vlanif(\d+)', line)
                if not tmp:
                    continue
                ip = ip_result['ip']
                vlan = "vlan" + tmp.group(1)
                tmp1 = re.search(r'description (.*)', line)
                description = tmp1.group(1).strip() if tmp1 else ''
                tmp2 = re.search(r'ip binding vpn-instance (.*)', line)
                vrf = tmp2.group(1).strip() if tmp2 else ''
                tmp3 = re.search(r'ip address ([0-9.]+) ([0-9.]+)', line)
                ip_addr = tmp3.group(1) + '/' + str(transform_subnet_mask(tmp3.group(2))) if tmp3 else ''
                ipv4_subnet = str(ipaddress.ip_network(ip_addr, strict=False)) if ip_addr else ''
                tmp4 = re.search(r'ipv6 address (\S+)', line)
                ipv6_addr = tmp4.group(1) if tmp4 else ''
                ipv6_subnet = str(ipaddress.ip_network(ipv6_addr, strict=False)) if ipv6_addr else ''
                lineInfo = ip + "@#" + vlan + "@#" + description + "@#" + vrf + "@#" + ipv4_subnet + "@#" + ipv6_subnet + "@#" + ip_addr + "@#" + ipv6_addr
                res_list.append(lineInfo)
        return res_list

    def formate_vlan_ne40e_x16a(org_data):
        res_list = []
        for ip_result in org_data:
            text = ip_result['tmp']
            for line in text.split('#\r\n'):
                et = re.search(r"interface Eth-Trunk11.(.+?)\r", line)
                if not et:  # 只取eth-trunk11.多的，11.多代表路由器下联eor交换机的，网络组暂时只需要下联关系，业务层vlan（互联）存在重复
                    continue
                tmp = re.search('vlan-type dot1q (.+?)\r', line)
                if not tmp:
                    continue
                ip = ip_result['ip']
                vlan = "vlan" + tmp.group(1)
                tmp1 = re.search(r'description (.*)', line)
                description = tmp1.group(1).strip() if tmp1 else ''
                tmp2 = re.search(r'ip binding vpn-instance (.*)', line)
                vrf = tmp2.group(1).strip() if tmp2 else ''
                tmp3 = re.search(r'ip address ([0-9.]+) ([0-9.]+)', line)
                ip_addr = tmp3.group(1) + '/' + str(transform_subnet_mask(tmp3.group(2))) if tmp3 else ''
                ipv4_subnet = str(ipaddress.ip_network(ip_addr, strict=False)) if ip_addr else ''
                tmp4 = re.search(r'ipv6 address (\S+)', line)
                ipv6_addr = tmp4.group(1) if tmp4 else ''
                ipv6_subnet = str(ipaddress.ip_network(ipv6_addr, strict=False)) if ipv6_addr else ''
                lineInfo = ip + "@#" + vlan + "@#" + description + "@#" + vrf + "@#" + ipv4_subnet + "@#" + ipv6_subnet + "@#" + ip_addr + "@#" + ipv6_addr
                res_list.append(lineInfo)
        return res_list

    def formate_vlan_f_9908(org_data):
        res_list = []
        for ip_result in org_data:
            text = ip_result['tmp']
            for line in text.split('$'):
                tmp = re.search('interface vlan(\d+)', line)
                if not tmp:
                    continue
                ip = ip_result['ip']
                vlan = "vlan" + tmp.group(1)
                tmp1 = re.search(r'description (.*)', line)
                description = tmp1.group(1).strip() if tmp1 else ''
                tmp2 = re.search(r'ip vrf forwarding (\S+)', line)
                vrf = tmp2.group(1) if tmp2 else ''
                tmp3 = re.search(r'ip address ([0-9.]+) ([0-9.]+)', line)
                ip_addr = tmp3.group(1) + '/' + str(transform_subnet_mask(tmp3.group(2))) if tmp3 else ''
                ipv4_subnet = str(ipaddress.ip_network(ip_addr, strict=False)) if ip_addr else ''
                tmp4 = re.search(r'ipv6 address (\S+)', line)
                ipv6_addr = tmp4.group(1) if tmp4 else ''
                ipv6_subnet = str(ipaddress.ip_network(ipv6_addr, strict=False)) if ipv6_addr else ''
                lineInfo = ip + "@#" + vlan + "@#" + description + "@#" + vrf + "@#" + ipv4_subnet + "@#" + ipv6_subnet + "@#" + ip_addr + "@#" + ipv6_addr
                res_list.append(lineInfo)
        return res_list

    def formate_vlan_m6000_18s(org_data):
        return formate_vlan_f_9908(org_data)

    def formate_vlan_ce6856(org_data):
        res_list = []
        for vl in org_data:
            cont = vl['tmp']
            vlan_vrf = cont.split("#")
            for i in vlan_vrf:
                stack_vlan = (' ').join(re.findall(r"stack-vlan (.+?)\r", i))
                if stack_vlan:
                    for v in list(set(stack_vlan.split(' '))):
                        lineInfo = vl["ip"] + "@#" + str(
                            v) + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + ""
                        res_list.append(lineInfo)
        return res_list

    def formate_vlan_f_5960_72dl_h(org_data):
        res_list = []
        for vl in org_data:
            logging.info('get vlan one cmd ret dict : %s' % vl)
            cont = vl['tmp']
            vlan_vrf = cont.split("#")
            for i in vlan_vrf:
                stack_vlan = re.findall(r"egress-outvlan (.+?)\r", i)
                logging.info('stack_vlan ret :%s' % stack_vlan)

                if stack_vlan:
                    for v in list(set(stack_vlan)):
                        lineInfo = vl["ip"] + "@#" + str(
                            v) + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + ""

                        logging.info('one stack_vlan :%s, lineInfo: %s' % (v, lineInfo))
                        res_list.append(lineInfo)

        logging.info('vlan list ret :%s' % res_list)
        return res_list

    # peach 迈普s4320-56tc
    def formate_vlan_s4320_56tc(org_data):
        res_list = []
        for data in org_data:
            # logging.info('get vlan maipu s4320-56tc one ip cmd ret dict : %s' % data)
            response = data['tmp']
            ip = data['ip']
            vlan_list = re.findall('VLAN\d+', response)
            logging.info('s4320-56tc find VLAN is :%s' % vlan_list)
            if vlan_list:
                for vlan in vlan_list:
                    nums = vlan.split('VLAN')[1]
                    if nums[0] == '0':
                        nums = nums[1:]
                    lineInfo = data[
                                   "ip"] + "@#" + nums + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + ""
                    res_list.append(lineInfo)
                    logging.info('one s4320-56tc vlan :%s, lineInfo: %s' % (ip, lineInfo))

            else:
                lineInfo = data[
                               "ip"] + "@#" + "@#" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + "" + "@#" + ""
                res_list.append(lineInfo)
                logging.info('one s4320-56tc vlan :%s, lineInfo: %s' % (ip, lineInfo))
            logging.info('-----------------------------------------华丽分割线--------------------------------------------')
        return res_list

    vlan_filename = "/tmp/data/" + 'DEVICE_VLAN_' + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'
    logging.info('vlan_filename info :%s' % vlan_filename)
    content = ["device_ip@#vlan@#description@#vrf@#ipv4_subnet@#ipv6_subnet@#ipv4_gateway@#ipv6_gateway"]

    logging.info('get vlan content info :%s' % content)
    for _type in type_ip:  # type key型号
        if _type not in vlan_cmd:
            continue
        logging.info('search vlan type  :%s' % _type)

        org_data_ips = copy.deepcopy(type_ip[_type])  # 要采集的所有IP，是个列表
        logging.info('collection vlan ips  :%s' % org_data_ips)

        org_data = collect_data(org_data_ips, _type, device_name, device_password, vlan_cmd[_type][0],
                                vlan_cmd[_type][1])

        formate_list = eval("formate_vlan_" + _type)(org_data)

        content.extend(formate_list)
    # tools_execution(vlan_filename, "\n".join(content))  # 执行工具将文件保存到指定设备
    # write_to_gz(vlan_filename, "\n".join(content))

    with open(vlan_filename, "w") as f:
        f.write("\n".join(content))


def get_vrf(type_ip):
    vrf_cmd = {"ce12808": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "ce16808": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "ne40e_x16a": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "ce6881_48s6cq": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "ce16816": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "ce6856_48s6q_hi": ["display ip vpn-instance", "vpn-instance[\S\s]+(#|>|\]) *$"],  # 华为
               "f_9908": ["show ip vrf brief", "show ip vrf brief[\S\s]+(#|>|\]) *$"],  # 中兴
               "m6000_18s": ["show ip vrf brief", "show ip vrf brief[\S\s]+(#|>|\]) *$"],  # 中兴
               "f_5960_72dl_h": ["show ip vrf brief", "show ip vrf brief[\S\s]+(#|>|\]) *$"]
               }

    def formate_vrf_ce6881_48s6cq(org_data):
        return formate_vrf_ce12808(org_data)

    def formate_vrf_ce6856_48s6q_hi(org_data):
        return formate_vrf_ce12808(org_data)

    def formate_vrf_ce16808(org_data):
        return formate_vrf_ce12808(org_data)

    def formate_vrf_ce12808(org_data):
        res_list = []
        for ip_result in org_data:
            text = ip_result['tmp']
            isBegin = False
            for line in text.split('\r\n'):
                tmp = re.search(r'Name', line)
                if tmp:
                    isBegin = True
                    continue
                if not isBegin:
                    continue
                tmp1 = re.search(r'(\S+)\s+(\<not set\>|[\d:]+)\s+(\S+|\s+)', line)
                if tmp1:
                    ip = ip_result['ip']
                    vrf = tmp1.group(1)
                    rd = tmp1.group(2)
                    addfamily = tmp1.group(3)
                    # lineInfo = ip + "@#" + vrf + "@#" + rd + "@#" + addfamily + "\n"
                    lineInfo = ip + "@#" + vrf + "@#" + ", ".join([ip + '_' + rd for ip in addfamily.split(',')])
                    res_list.append(lineInfo)
        return res_list

    def formate_vrf_ne40e_x16a(org_data):
        return formate_vrf_ce12808(org_data)

    def formate_vrf_f_5960_72dl_h(org_data):
        return formate_vrf_f_9908(org_data)

    def formate_vrf_f_9908(org_data):
        res_list = []
        for ip_result in org_data:
            logging.info('get vrf one cmd ret dict : %s' % ip_result)
            text = ip_result['tmp']
            isBegin = False
            for line in text.split('\r\n'):
                tmp = re.search(r'Name', line)
                if tmp:
                    isBegin = True
                    continue
                if not isBegin:
                    continue
                tmp1 = re.search(r'(\S+)\s+(\<not set\>|[\d:]+)\s+(\S+|\s+)', line)
                if tmp1:
                    ip = ip_result['ip']
                    vrf = tmp1.group(1)
                    rd = tmp1.group(2)
                    addfamily = tmp1.group(3)
                    # lineInfo = ip + "@#" + vrf + "@#" + rd + "@#" + addfamily + "\n"
                    lineInfo = ip + "@#" + vrf + "@#" + ", ".join([ip + '_' + rd for ip in addfamily.split(',')])
                    logging.info('one name :%s, lineInfo: %s' % (tmp, lineInfo))
                    res_list.append(lineInfo)
        logging.info('vrf list ret :%s' % res_list)
        return res_list

    def formate_vrf_m6000_18s(org_data):
        return formate_vrf_f_9908(org_data)

    vrf_filename = "/tmp/data/" + 'DEVICE_VRF_RD_' + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'
    logging.info('vlan_filename info :%s' % vrf_filename)
    content = ["device_ip@#vrf@#rd"]
    logging.info('get vrf content info :%s' % content)
    for _type in type_ip:
        if _type not in vrf_cmd:
            continue
        logging.info('search vrf type  :%s' % _type)
        org_data_ips = copy.deepcopy(type_ip[_type])
        logging.info('collection vrf ips  :%s' % org_data_ips)

        org_data = collect_data(org_data_ips, _type, device_name, device_password, vrf_cmd[_type][0],
                                vrf_cmd[_type][1])
        logging.info('all get_vrf ips ret info %s' % org_data)
        formate_list = eval("formate_vrf_" + _type)(org_data)
        content.extend(formate_list)

    # tools_execution(vrf_filename, "\n".join(content))  # 执行工具将文件保存到指定设备
    # write_to_gz(vrf_filename, "\n".join(content))
    with open(vrf_filename, "w") as f:
        f.write("\n".join(content))


def get_port_vlan(type_ip):
    port_vlan_cmd = {
        "f_9908": ["show running-config switchvlan", "show lacp counters", "[\S\s]+(#|>|\]) *$"],  # ZET
        "f_5960_72dl_h": ["show running-config switchvlan", "show lacp counters", "[\S\s]+(#|>|\]) *$"],  # ZET
        "f_5960": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],  # ZET
        "ce12808": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],  # Huawei
        "ce16808": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],  # Huawei
        "ce6856": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],  # Huawei
        "ce6881_48s6cq": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],  # Huawei
        "ce6856_48s6q_hi": ["dis port vlan", "dis interface Eth-Trunk", "[\S\s]+(#|>|\]) *$"],
        # "ce16816": ["dis port vlan", "dis Eth-Trunk", "[\S\s]+(#|>|\]) *$"]  没数据 不查
    }

    def formate_port_vlan_f_5960(org_data, org_prot):
        return formate_port_vlan_f_9908(org_data, org_prot)

    def formate_port_vlan_ce6856(org_data, org_prot):
        return formate_port_vlan_ce12808(org_data, org_prot)

    def formate_port_vlan_ce16808(org_data, org_prot):
        return formate_port_vlan_ce12808(org_data, org_prot)

    def formate_port_vlan_ce6856_48s6q_hi(org_data, org_prot):
        return formate_port_vlan_ce12808(org_data, org_prot)

    def formate_port_vlan_ce6881_48s6cq(org_data, org_prot):
        return formate_port_vlan_ce12808(org_data, org_prot)

    def formate_port_vlan_ce12808(org_data, org_prot):
        vlan_lists = []
        results = org_prot
        for vl in results:
            cont = vl['tmp']
            st = cont.split('\r\n\r\n')
            for i in st:
                vlan_list = {}
                tr = re.search(r"(Eth-Trunk\d+)\b", i)
                portname = re.findall(r'(\d+[A-Z]+\d+/\S+)\b', i)

                if tr:
                    trunck = (tr.group(1))
                    # print(vl['ip'],'--------',trunck,'------',portname)
                    vlan_list = {
                        "ipv6": vl['ip'],
                        "trunck": trunck,
                        "portname": portname
                    }
                    vlan_lists.append(vlan_list)

        res_list = []
        vlan_list_port = {}
        vlan_list_trunk = {}
        port_vlan_list = []

        results = org_data
        trunkport = vlan_lists

        for vl in results:
            cont = vl['tmp']

            vl_cont = cont[cont.rfind('--------'):-1]

            st = vl_cont.split('\r\n')

            for i in st:
                # tmp = re.search(r'(\S+)\s+([a-z-]+)\s+(\d+)\s+(.*)\s{2,}(.*)\s', i)
                tmp = re.search(r'(\S+)\s+([a-z-]+)\s+(\d+)\s+(.*)\s{2,}(.*)\s', i)

                if tmp:
                    # port = re.sub('[\x1b]+', '', tmp.group(1))
                    port = re.sub(u"(\x1b\[16D)", "", tmp.group(1))
                    trunkvlanlist = tmp.group(4)

                    if "Eth-" not in port and '-- ' not in trunkvlanlist:
                        vlan_list_port = {
                            "ipv6": vl['ip'],
                            "port": port,
                            "trunkvlanlist": trunkvlanlist
                        }
                        res_list.append(vlan_list_port)
                    if "Eth-" in port and '-- ' not in trunkvlanlist:

                        for j in trunkport:
                            if j['trunck'] == port and j['ipv6'] == vl['ip']:

                                for o in j['portname']:
                                    vlan_list_trunk = {
                                        "ipv6": vl['ip'],
                                        "port": o,
                                        "trunkvlanlist": trunkvlanlist
                                    }
                                    res_list.append(vlan_list_trunk)

        for t in res_list:
            st_l = t['ipv6'] + "@#" + str(t["port"]) + "@#" + str(t["trunkvlanlist"])
            port_vlan_list.append(st_l)
        return port_vlan_list

    def formate_port_vlan_f_9908(org_data, org_prot):
        vlan_lists = []
        vls = {}
        portdata = org_prot
        for vl in portdata:
            cont = vl['tmp']
            # raise KeyError(cont)
            st = re.split(r'\r\n(?=Smartgroup)', cont)

            for i in st:
                tmp = re.search(r'Smartgroup:([0-9]+)', i)
                port = re.findall(r'[A-Za-z]+\-+[0-9]+\/+\S+', i)

                for j in port:
                    vls = {
                        "port": j,
                        "group": 'smartgroup' + tmp.group(1)
                    }
                    vlan_lists.append(vls)

        # print(vlan_lists)
        vlan_list = []
        vlan = ""
        results = org_data
        trunkport = vlan_lists

        for vl in results:
            cont = vl['tmp']
            if cont:
                vlan_vrf = cont.split("$")
                for i in vlan_vrf:

                    port = re.findall(r"interface (.+?)\r", i)

                    # description = re.findall(r"description (.+?)\r", i)
                    vlan_trunk = re.findall(r"switchport trunk vlan (.+?)\r", i)
                    vlan_hybrid = re.findall(r"switchport hybrid vlan (.+?)\r", i)
                    trunk_pvid = re.findall(r"switchport trunk native vlan (.+?)\r", i)
                    hybrid_pvid = re.findall(r"switchport hybrid native vlan (.+?)\r", i)
                    if vlan_trunk:
                        vlan = vlan_trunk
                    if vlan_hybrid:
                        vlan = vlan_hybrid
                    if trunk_pvid:
                        pvid = trunk_pvid

                    if hybrid_pvid:
                        pvid = hybrid_pvid

                    if vlan:
                        if len(vlan) > 1:

                            vt = "|".join(vlan)
                        else:
                            vt = vlan[0]
                    else:
                        vt = ""
                    if port:
                        if "smartgroup" not in port[0]:
                            tr = vl["ip"] + "@#" + port[0] + "@#" + vt
                            vlan_list.append(tr)
                        else:

                            for j in trunkport:
                                if port[0] == j["group"]:
                                    tr = vl["ip"] + "@#" + j["port"] + "@#" + vt
                                    vlan_list.append(tr)
        return vlan_list

    def formate_port_vlan_f_5960_72dl_h(org_data, org_prot):
        return formate_port_vlan_f_9908(org_data, org_prot)

    vrf_filename = "/tmp/data/" + 'DEVICE_PORT_VLAN_' + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'
    content = ["ipv6@#port_l@#trunkvlanlist"]
    for _type in type_ip:
        if _type not in port_vlan_cmd:
            continue
        org_data_ips = copy.deepcopy(type_ip[_type])
        org_prot_ips = copy.deepcopy(type_ip[_type])
        org_data = collect_data(org_data_ips, _type, device_name, device_password, port_vlan_cmd[_type][0],
                                port_vlan_cmd[_type][2])
        org_prot = collect_data(org_prot_ips, _type, device_name, device_password, port_vlan_cmd[_type][1],
                                port_vlan_cmd[_type][2])
        formate_list = eval("formate_port_vlan_" + _type)(org_data, org_prot)
        content.extend(formate_list)

    # tools_execution(vrf_filename, "\n".join(content))  # 执行工具将文件保存到指定设备
    # write_to_gz(vrf_filename, "\n".join(content))
    with open(vrf_filename, "w") as f:
        f.write("\n".join(content))


if __name__ == '__main__':
    # 数通设备账号密码
    device_name = "cmdb_col"
    device_password = "Kh&3175Wu"
    # {"型号":[ip1, ip2]}
    model_ip = {
        # "f_5960_72dl_h": ['2409:8086:8514:80:0:0:0:10', ]
        # "f_5960_72dl_h":  # 可信4   网管池1 超时   采集机器10.211.202.62  NFV-R-HDNJH-03A-HW-01-VM-ZJ-Smartping-Gb
        #     ['2409:8086:8514:80:0:0:0:10', '2409:8086:8514:80:0:0:0:11', '2409:8086:8514:80:0:0:0:12',
        #      '2409:8086:8514:80:0:0:0:13', '2409:8086:8514:80:0:0:0:14', '2409:8086:8514:80:0:0:0:15',
        #      '2409:8086:8514:80:0:0:0:16', '2409:8086:8514:80:0:0:0:17', '2409:8086:8514:80:0:0:0:18',
        #      '2409:8086:8514:80:0:0:0:19', '2409:8086:8514:80:0:0:0:1a', '2409:8086:8514:80:0:0:0:1b',
        #      '2409:8086:8514:80:0:0:0:1c', '2409:8086:8514:80:0:0:0:1d', '2409:8086:8514:80:0:0:0:1e',
        #      '2409:8086:8514:80:0:0:0:1f', '2409:8086:8514:80:0:0:0:20', '2409:8086:8514:80:0:0:0:21',
        #      '2409:8086:8514:80:0:0:0:22', '2409:8086:8514:80:0:0:0:23', '2409:8086:8514:80:0:0:0:24',
        #      '2409:8086:8514:80:0:0:0:25', '2409:8086:8514:80:0:0:0:26', '2409:8086:8514:80:0:0:0:27',
        #      '2409:8086:8514:80:0:0:0:28', '2409:8086:8514:80:0:0:0:29', '2409:8086:8514:80:0:0:0:2a',
        #      '2409:8086:8514:80:0:0:0:2b', '2409:8086:8514:80:0:0:0:2c', '2409:8086:8514:80:0:0:0:2d',
        #      '2409:8086:8514:80:0:0:0:2e', '2409:8086:8514:80:0:0:0:2f', '2409:8086:8514:80:0:0:0:30',
        #      '2409:8086:8514:80:0:0:0:31', '2409:8086:8514:80:0:0:0:32', '2409:8086:8514:80:0:0:0:33',
        #      '2409:8086:8514:80:0:0:0:34', '2409:8086:8514:80:0:0:0:35', '2409:8086:8514:80:0:0:0:36',
        #      '2409:8086:8514:80:0:0:0:37', '2409:8086:8514:80:0:0:0:38', '2409:8086:8514:80:0:0:0:39',
        #      '2409:8086:8514:80:0:0:0:3a', '2409:8086:8514:80:0:0:0:3b', '2409:8086:8514:80:0:0:0:3c',
        #      '2409:8086:8514:80:0:0:0:3d', '2409:8086:8514:80:0:0:0:3e', '2409:8086:8514:80:0:0:0:3f',
        #      '2409:8086:8514:80:0:0:0:40', '2409:8086:8514:80:0:0:0:41', '2409:8086:8514:80:0:0:0:42',
        #      '2409:8086:8514:80:0:0:0:43', '2409:8086:8514:80:0:0:0:44', '2409:8086:8514:80:0:0:0:45',
        #      '2409:8086:8514:80:0:0:0:46', '2409:8086:8514:80:0:0:0:47', '2409:8086:8514:80:0:0:0:48',
        #      '2409:8086:8514:80:0:0:0:49', '2409:8086:8514:80:0:0:0:4a', '2409:8086:8514:80:0:0:0:4b',
        #      '2409:8086:8514:80:0:0:0:4c', '2409:8086:8514:80:0:0:0:4d', '2409:8086:8514:80:0:0:0:4e',
        #      '2409:8086:8514:80:0:0:0:4f', '2409:8086:8514:80:0:0:0:50', '2409:8086:8514:80:0:0:0:51',
        #      '2409:8086:8514:80:0:0:0:52', '2409:8086:8514:80:0:0:0:53', '2409:8086:8514:80:0:0:0:54',
        #      '2409:8086:8514:80:0:0:0:55', '2409:8086:8514:80:0:0:0:56', '2409:8086:8514:80:0:0:0:57',
        #      '2409:8086:8514:80:0:0:0:58', '2409:8086:8514:80:0:0:0:59', '2409:8086:8514:80:0:0:0:5a',
        #      '2409:8086:8514:80:0:0:0:5b', '2409:8086:8514:80:0:0:0:5c', '2409:8086:8514:80:0:0:0:5d',
        #      '2409:8086:8514:80:0:0:0:5e', '2409:8086:8514:80:0:0:0:5f', '2409:8086:8514:80:0:0:0:60',
        #      '2409:8086:8514:80:0:0:0:61', '2409:8086:8514:80:0:0:0:62', '2409:8086:8514:80:0:0:0:63',
        #      '2409:8086:8514:80:0:0:0:64', '2409:8086:8514:80:0:0:0:65', '2409:8086:8514:80:0:0:0:66',
        #      '2409:8086:8514:80:0:0:0:67', '2409:8086:8514:80:0:0:0:68', '2409:8086:8514:80:0:0:0:69',
        #      '2409:8086:8514:80:0:0:0:6a', '2409:8086:8514:80:0:0:0:6b', '2409:8086:8514:80:0:0:0:6c',
        #      '2409:8086:8514:80:0:0:0:6d', '2409:8086:8514:80:0:0:0:6e', '2409:8086:8514:80:0:0:0:6f',
        #      '2409:8086:8514:80:0:0:0:70', '2409:8086:8514:80:0:0:0:71', '2409:8086:8514:80:0:0:0:72',
        #      '2409:8086:8514:80:0:0:0:73', '2409:8086:8514:80:0:0:0:74', '2409:8086:8514:80:0:0:0:75',
        #      '2409:8086:8514:80:0:0:0:76', '2409:8086:8514:80:0:0:0:77', '2409:8086:8514:80:0:0:0:78',
        #      '2409:8086:8514:80:0:0:0:79', '2409:8086:8514:80:0:0:0:7a', '2409:8086:8514:80:0:0:0:7b',
        #      '2409:8086:8514:80:0:0:0:7c', '2409:8086:8514:80:0:0:0:7d', '2409:8086:8514:80:0:0:0:7e',
        #      '2409:8086:8514:80:0:0:0:7f', '2409:8086:8514:80:0:0:0:80', '2409:8086:8514:80:0:0:0:81',
        #      '2409:8086:8514:80:0:0:0:82', '2409:8086:8514:80:0:0:0:83', '2409:8086:8514:80:0:0:0:84',
        #      '2409:8086:8514:80:0:0:0:85', '2409:8086:8514:80:0:0:0:86', '2409:8086:8514:80:0:0:0:87',
        #      '2409:8086:8514:80:0:0:0:88', '2409:8086:8514:80:0:0:0:89', '2409:8086:8514:80:0:0:0:8a',
        #      '2409:8086:8514:80:0:0:0:8b', '2409:8086:8514:80:0:0:0:8c', '2409:8086:8514:80:0:0:0:8d',
        #      '2409:8086:8514:80:0:0:0:8e', '2409:8086:8514:80:0:0:0:8f', '2409:8086:8514:80:0:0:0:90',
        #      '2409:8086:8514:80:0:0:0:91', '2409:8086:8514:80:0:0:0:92', '2409:8086:8514:80:0:0:0:93',
        #      '2409:8086:8514:80:0:0:0:94', '2409:8086:8514:80:0:0:0:95', '2409:8086:8514:80:0:0:0:96',
        #      '2409:8086:8514:80:0:0:0:97', '2409:8086:8514:80:0:0:0:98', '2409:8086:8514:80:0:0:0:99',
        #      '2409:8086:8514:80:0:0:0:9a', '2409:8086:8514:80:0:0:0:9b', '2409:8086:8514:80:0:0:0:9c',
        #      '2409:8086:8514:80:0:0:0:f'],

        # "f_9908":  # 可信4        网管池1 超时  采集机器 10.211.202.62  NFV-R-HDNJH-03A-HW-01-VM-ZJ-Smartping-Gb
        #     ['2409:8086:8514:80:0:0:0:1', '2409:8086:8514:80:0:0:0:2', '2409:8086:8514:80:0:0:0:3',
        #      '2409:8086:8514:80:0:0:0:4', '2409:8086:8514:80:0:0:0:5', '2409:8086:8514:80:0:0:0:6']

        # "5952D":  # 2台机器都超时连接
        #   ["2409:8086:8521:a4::80"]
        # "f_5960_72dl_h": ["2409:8086:8514:0080::88"]

        "s4320_56tc": ['2409:8086:8514:80:0:0:0:9d', '2409:8086:8514:80:0:0:0:9e', '2409:8086:8514:80:0:0:0:9f',
                       '2409:8086:8514:80:0:0:0:a0', '2409:8086:8514:80:0:0:0:a1', '2409:8086:8514:80:0:0:0:a2',
                       '2409:8086:8514:80:0:0:0:a3', '2409:8086:8514:80:0:0:0:a4', '2409:8086:8514:80:0:0:0:a5',
                       '2409:8086:8514:80:0:0:0:a6', '2409:8086:8514:80:0:0:0:a7', '2409:8086:8514:80:0:0:0:a8',
                       '2409:8086:8514:80:0:0:0:a9', '2409:8086:8514:80:0:0:0:aa', '2409:8086:8514:80:0:0:0:ab',
                       '2409:8086:8514:80:0:0:0:ac', '2409:8086:8514:80:0:0:0:ad', '2409:8086:8514:80:0:0:0:ae',
                       '2409:8086:8514:80:0:0:0:af', '2409:8086:8514:80:0:0:0:b0', '2409:8086:8514:80:0:0:0:b1',
                       '2409:8086:8514:80:0:0:0:b2', '2409:8086:8514:80:0:0:0:b3', '2409:8086:8514:80:0:0:0:b4',
                       '2409:8086:8514:80:0:0:0:b5', '2409:8086:8514:80:0:0:0:b6', '2409:8086:8514:80:0:0:0:b7',
                       '2409:8086:8514:80:0:0:0:b8', '2409:8086:8514:80:0:0:0:b9', '2409:8086:8514:80:0:0:0:ba',
                       '2409:8086:8514:80:0:0:0:bb', '2409:8086:8514:80:0:0:0:bc', '2409:8086:8514:80:0:0:0:bd',
                       '2409:8086:8514:80:0:0:0:be', '2409:8086:8514:80:0:0:0:bf', '2409:8086:8514:80:0:0:0:c0',
                       '2409:8086:8514:80:0:0:0:c1', '2409:8086:8514:80:0:0:0:c2', '2409:8086:8514:80:0:0:0:c3',
                       '2409:8086:8514:80:0:0:0:c4', '2409:8086:8514:80:0:0:0:c5', '2409:8086:8514:80:0:0:0:c6',
                       '2409:8086:8514:80:0:0:0:c7', '2409:8086:8514:80:0:0:0:c8', '2409:8086:8514:80:0:0:0:c9',
                       '2409:8086:8514:80:0:0:0:ca', '2409:8086:8514:80:0:0:0:cb']

    }

    # source_list = ["vlan", "vrf", "port_vlan"]
    source_list = ["vlan"]
    # source_list = ["vrf"]['', '2409:8086:8514:0080::1', '2409:8086:8514:0080::2', '2409:8086:8514:0080::3', '2409:8086:8514:0080::4', '2409:8086:8514:0080::5', '2409:8086:8514:0080::6', '']
    for _func in source_list:
        eval("get_" + _func)(model_ip)
