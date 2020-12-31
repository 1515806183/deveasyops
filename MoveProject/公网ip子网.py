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
        self.timeout = kwargs['timeout'] if 'timeout' in kwargs else 100
        self.banner_timeout = kwargs['banner_timeout'] if 'banner_timeout' in kwargs else 300
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
            # print("timeout {}".format(ip))
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


def get_public_ip(type_ip):
    logging.info('start get_public_ip...............')

    def zx_9908(ipv4_inters, ipv6_inters, inter_brief):

        # 1. 处理 org_data
        ip_result = []
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
                        line_info = [device2["ip"], interface, ip_addr.split(",")[-1].split("/")[0], "ipv6"]
                        ip_result.append(line_info)
                except Exception as e:
                    continue

        inter_result = []
        for device3 in inter_brief:
            try:
                isBreak = True
                for line3 in re.split(r'\r\n', device3["tmp"]):
                    # Interface                       AdminStatus  PhyStatus  Protocol  Description
                    # xgei-0/0/0/1                    up           up         up        TO-NFV-D-HNGZ-00A-2501-AD08-S-DDOS-01-tengige1_0-10G
                    temp = re.search(r'Interface\s+Admin', line3)
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

        result = []
        for ip in ip_result:
            if "loopback" in ip[1].lower():
                temp = ip[:]
                temp.append("loopback")
                temp1 = "@#$".join(temp)
                result.append(temp1)
                continue
            for inter in inter_result:
                try:
                    if ip[0] == inter[0] and ip[1] == inter[1]:
                        temp = ip[:]
                        temp1 = "@#$".join(temp)
                        result.append(temp1)
                except Exception as e:
                    continue

        return result

    def zx_5960_72dl_h(ipv4_inters, ipv6_inters, inter_brief):
        return zx_9908(ipv4_inters, ipv6_inters, inter_brief)

    public_ip_cmd = {
        "zx_9908": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                    "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],  # ZET

        "zx_5960_72dl_h": ["show ip interface brief", "show ipv6 interface brief", "show interface des",
                           "interface brief[\S\s]+(#|>|\]) *$", "interface des[\S\s]+(#|>|\]) *$"],  # ZET

    }

    vrf_filename = "/tmp/data/" + 'DEVICE_PUBLIC_IP_' + '_' + datetime.datetime.now().strftime('%Y%m%d') + '.csv'

    content = ["device_ip@#$interface@#$ip_addr@#$type@#$purpose"]
    formate_list = ''

    for _type in type_ip:
        logging.info('get_public_ip The model of collection is: %s' % _type)
        if _type not in public_ip_cmd:
            continue
        ipv4_inters_ips = copy.deepcopy(type_ip[_type])
        ipv6_inters_ips = copy.deepcopy(type_ip[_type])
        inter_brief_ips = copy.deepcopy(type_ip[_type])

        logging.info('get_public_ip Collected IP is :%s' % type_ip[_type])

        logging.info('ipv4_inters Command to start execution... %s:' % public_ip_cmd[_type][0])
        ipv4_inters = collect_data(ipv4_inters_ips, _type, device_name, device_password, public_ip_cmd[_type][0],
                                   public_ip_cmd[_type][2])

        logging.info('ipv6_inters Command to start execution... %s:' % public_ip_cmd[_type][1])
        ipv6_inters = collect_data(ipv6_inters_ips, _type, device_name, device_password, public_ip_cmd[_type][1],
                                   public_ip_cmd[_type][2])

        logging.info('inter_brief Command to start execution... %s:' % public_ip_cmd[_type][2])
        inter_brief = collect_data(inter_brief_ips, _type, device_name, device_password, public_ip_cmd[_type][2],
                                   public_ip_cmd[_type][2])

        logging.info('------get_public_ip The execution of the command ends and begins to parse the data------')

        formate_list = eval(str(_type))(ipv4_inters, ipv6_inters, inter_brief)

        content.extend(formate_list)

    # 保存为cvs
    with open(vrf_filename, "w") as f:
        f.write("\n".join(content))


if __name__ == '__main__':
    # 数通设备账号密码
    device_name = "cmdb_col"
    device_password = "Kh&3175Wu"
    # {"型号":[ip1, ip2]} # '2409:8086:8514:80:0:0:0:11'
    model_ip = {
        "zx_9908": ['2409:8086:8514:80:0:0:0:1', '2409:8086:8514:80:0:0:0:2', '2409:8086:8514:80:0:0:0:3',
                    '2409:8086:8514:80:0:0:0:4', '2409:8086:8514:80:0:0:0:5', '2409:8086:8514:80:0:0:0:6'],
        "zx_5960_72dl_h": ['2409:8086:8514:80:0:0:0:10', '2409:8086:8514:80:0:0:0:11', '2409:8086:8514:80:0:0:0:12', '2409:8086:8514:80:0:0:0:13', '2409:8086:8514:80:0:0:0:14', '2409:8086:8514:80:0:0:0:15', '2409:8086:8514:80:0:0:0:16', '2409:8086:8514:80:0:0:0:17', '2409:8086:8514:80:0:0:0:18', '2409:8086:8514:80:0:0:0:19', '2409:8086:8514:80:0:0:0:1a', '2409:8086:8514:80:0:0:0:1b', '2409:8086:8514:80:0:0:0:1c', '2409:8086:8514:80:0:0:0:1d', '2409:8086:8514:80:0:0:0:1e', '2409:8086:8514:80:0:0:0:1f', '2409:8086:8514:80:0:0:0:20', '2409:8086:8514:80:0:0:0:21', '2409:8086:8514:80:0:0:0:22', '2409:8086:8514:80:0:0:0:23', '2409:8086:8514:80:0:0:0:24', '2409:8086:8514:80:0:0:0:25', '2409:8086:8514:80:0:0:0:26', '2409:8086:8514:80:0:0:0:27', '2409:8086:8514:80:0:0:0:28', '2409:8086:8514:80:0:0:0:29', '2409:8086:8514:80:0:0:0:2a', '2409:8086:8514:80:0:0:0:2b', '2409:8086:8514:80:0:0:0:2c', '2409:8086:8514:80:0:0:0:2d', '2409:8086:8514:80:0:0:0:2e', '2409:8086:8514:80:0:0:0:2f', '2409:8086:8514:80:0:0:0:30', '2409:8086:8514:80:0:0:0:31', '2409:8086:8514:80:0:0:0:32', '2409:8086:8514:80:0:0:0:33', '2409:8086:8514:80:0:0:0:34', '2409:8086:8514:80:0:0:0:35', '2409:8086:8514:80:0:0:0:36', '2409:8086:8514:80:0:0:0:37', '2409:8086:8514:80:0:0:0:38', '2409:8086:8514:80:0:0:0:39', '2409:8086:8514:80:0:0:0:3a', '2409:8086:8514:80:0:0:0:3b', '2409:8086:8514:80:0:0:0:3c', '2409:8086:8514:80:0:0:0:3d', '2409:8086:8514:80:0:0:0:3e', '2409:8086:8514:80:0:0:0:3f', '2409:8086:8514:80:0:0:0:40', '2409:8086:8514:80:0:0:0:41', '2409:8086:8514:80:0:0:0:42', '2409:8086:8514:80:0:0:0:43', '2409:8086:8514:80:0:0:0:44', '2409:8086:8514:80:0:0:0:45', '2409:8086:8514:80:0:0:0:46', '2409:8086:8514:80:0:0:0:47', '2409:8086:8514:80:0:0:0:48', '2409:8086:8514:80:0:0:0:49', '2409:8086:8514:80:0:0:0:4a', '2409:8086:8514:80:0:0:0:4b', '2409:8086:8514:80:0:0:0:4c', '2409:8086:8514:80:0:0:0:4d', '2409:8086:8514:80:0:0:0:4e', '2409:8086:8514:80:0:0:0:4f', '2409:8086:8514:80:0:0:0:50', '2409:8086:8514:80:0:0:0:51', '2409:8086:8514:80:0:0:0:52', '2409:8086:8514:80:0:0:0:53', '2409:8086:8514:80:0:0:0:54', '2409:8086:8514:80:0:0:0:55', '2409:8086:8514:80:0:0:0:56', '2409:8086:8514:80:0:0:0:57', '2409:8086:8514:80:0:0:0:58', '2409:8086:8514:80:0:0:0:59', '2409:8086:8514:80:0:0:0:5a', '2409:8086:8514:80:0:0:0:5b', '2409:8086:8514:80:0:0:0:5c', '2409:8086:8514:80:0:0:0:5d', '2409:8086:8514:80:0:0:0:5e', '2409:8086:8514:80:0:0:0:5f', '2409:8086:8514:80:0:0:0:60', '2409:8086:8514:80:0:0:0:61', '2409:8086:8514:80:0:0:0:62', '2409:8086:8514:80:0:0:0:63', '2409:8086:8514:80:0:0:0:64', '2409:8086:8514:80:0:0:0:65', '2409:8086:8514:80:0:0:0:66', '2409:8086:8514:80:0:0:0:67', '2409:8086:8514:80:0:0:0:68', '2409:8086:8514:80:0:0:0:69', '2409:8086:8514:80:0:0:0:6a', '2409:8086:8514:80:0:0:0:6b', '2409:8086:8514:80:0:0:0:6c', '2409:8086:8514:80:0:0:0:6d', '2409:8086:8514:80:0:0:0:6e', '2409:8086:8514:80:0:0:0:6f', '2409:8086:8514:80:0:0:0:70', '2409:8086:8514:80:0:0:0:71', '2409:8086:8514:80:0:0:0:72', '2409:8086:8514:80:0:0:0:73', '2409:8086:8514:80:0:0:0:74', '2409:8086:8514:80:0:0:0:75', '2409:8086:8514:80:0:0:0:76', '2409:8086:8514:80:0:0:0:77', '2409:8086:8514:80:0:0:0:78', '2409:8086:8514:80:0:0:0:79', '2409:8086:8514:80:0:0:0:7a', '2409:8086:8514:80:0:0:0:7b', '2409:8086:8514:80:0:0:0:7c', '2409:8086:8514:80:0:0:0:7d', '2409:8086:8514:80:0:0:0:7e', '2409:8086:8514:80:0:0:0:7f', '2409:8086:8514:80:0:0:0:80', '2409:8086:8514:80:0:0:0:81', '2409:8086:8514:80:0:0:0:82', '2409:8086:8514:80:0:0:0:83', '2409:8086:8514:80:0:0:0:84', '2409:8086:8514:80:0:0:0:85', '2409:8086:8514:80:0:0:0:86', '2409:8086:8514:80:0:0:0:87', '2409:8086:8514:80:0:0:0:88', '2409:8086:8514:80:0:0:0:89', '2409:8086:8514:80:0:0:0:8a', '2409:8086:8514:80:0:0:0:8b', '2409:8086:8514:80:0:0:0:8c', '2409:8086:8514:80:0:0:0:8d', '2409:8086:8514:80:0:0:0:8e', '2409:8086:8514:80:0:0:0:8f', '2409:8086:8514:80:0:0:0:90', '2409:8086:8514:80:0:0:0:91', '2409:8086:8514:80:0:0:0:92', '2409:8086:8514:80:0:0:0:93', '2409:8086:8514:80:0:0:0:94', '2409:8086:8514:80:0:0:0:95', '2409:8086:8514:80:0:0:0:96', '2409:8086:8514:80:0:0:0:97', '2409:8086:8514:80:0:0:0:98', '2409:8086:8514:80:0:0:0:99', '2409:8086:8514:80:0:0:0:9a', '2409:8086:8514:80:0:0:0:9b', '2409:8086:8514:80:0:0:0:9c', '2409:8086:8514:80:0:0:0:f', '2409:8086:8514:80:0:0:0:cc', '2409:8086:8514:80:0:0:0:cf', '2409:8086:8514:80:0:0:0:cd', '2409:8086:8514:80:0:0:0:d0', '2409:8086:8514:80:0:0:0:ce', '2409:8086:8514:80:0:0:0:d1', '2409:8086:8514:80:0:0:0:d2', '2409:8086:8514:80:0:0:0:d5', '2409:8086:8514:80:0:0:0:d3', '2409:8086:8514:80:0:0:0:d6', '2409:8086:8514:80:0:0:0:d4', '2409:8086:8514:80:0:0:0:d7']

    }
    # source_list = ["vlan", "vrf", "port_vlan"]
    source_list = ["public_ip"]
    for _func in source_list:
        eval("get_" + _func)(model_ip)
