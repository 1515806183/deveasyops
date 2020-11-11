# -*- coding: utf-8 -*-
"""
功能：通过psutil获取系统上的进程信息，包括pid，名称，路径，cpu，内存，网络连接等
依赖:
    psutil
设计：
    可获取指定进程的监听端口，检测端口连接数
    可获取指定进程的相关信息，如运行目录，执行命令，使用文件等
    支持根据pid寻找相符的pid，ppid
    支持根据进程名进行模糊查找
    支持根据程序路径进行查找，绝对路径
备注：
    输入参数
        pid, 进程的pid或ppid
        name, 包含该名字的进程
        app_path，可执行路径在该路径下的进程
    输出参数
        name:           进程名字
        pid:            进程id
        ppid:           父进程id
        status:         状态
        username:       执行用户
        cmdline:        启动命令
        exe:            可执行文件
        listen_port:    进程监听端口
        port_connections:  端口连接数, 通过connections获取
        memory:        内存占用比例
        cpu:            cpu占用比例
        open_files:     使用文件数,默认只显示5个
        file_list:      使用的文件详情，默认只显示5个
        current_work_dir: 应用启动目录
        num_threads:     线程数
"""
import urllib, requests
import psutil
import socket
import logging

FORMAT = '[%(asctime)s %(funcName)s %(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)
logger = logging.getLogger("app_check")


def set_files_blank(procs_info):
    """
    为了便于输出，将路径信息设置为空
    :param procs_info:
    :return:
    """
    filter_list = []

    for proc in procs_info:
        if "cmdline" in proc:
            proc["cmdline"] = ""
        if "file_list" in proc:
            proc["file_list"] = []
        filter_list.append(proc)
    return filter_list


def filter_proc(proc_info):
    """
    对进程进行过滤
    :param proc_info:
    :return: 过滤该进程返回True, 否则返回False
    """
    try:
        assert isinstance(proc_info, dict) and 'name' in proc_info
        # do some jduge with this proc_info
        return False
    except Exception as e:
        logger.error("filter_proc: {}".format(proc_info))
        return True


def search_port(port, procs_info):
    name_info = []
    for proc in procs_info:
        if port in proc.get("listen_port", ""):
            name_info.append(proc)
            # logger.info("get app_path proc info length {}".format(len(name_info)))
    return name_info


def search_name(name, procs_info):
    """
    根据进程名进行模糊查找
    :param name:
    :param procs_info:
    :return:
    """
    # logger.info("start to search name {}".format(name))
    name = name.strip()
    name_info = []
    for proc in procs_info:
        if name in proc.get("name", ""):
            name_info.append(proc)

    # logger.info("get app_path proc info length {}".format(len(name_info)))
    return name_info


# 进程信息收集
def collect_process_info():
    # Todo: 目前采集信息为单进程，pid，port均只有一个
    logger.info("start to collect process info...")
    custom_procs_info = []

    for proc in psutil.process_iter():
        try:
            custom_proc_info = {
                "ip": EASYOPS_LOCAL_IP,
                "name": "",
                "pid": 0,
                "ppid": 0,
                "status": "",
                "username": "",
                "cmdline": "",
                "listen_port": 0,
                "port_connections": 0,
                "memory": 0,
                "cpu": 0
            }
            # proc_info = proc.as_dict()
            all_port = []
            proc_info = proc.as_dict(
                attrs=['name', 'pid', 'ppid', 'status', 'username', 'cmdline', 'connections', 'memory_percent',
                       'cpu_percent'])
            # proc_info = proc.as_dict(attrs=['connections'])
            # print proc_info
            if not isinstance(proc_info, dict):
                logger.error("proc_info type error, type: {}, value: {}".format(type(proc_info), proc_info))
            try:
                custom_proc_info['name'] = proc_info.get("name", "Unknown")
                custom_proc_info['pid'] = proc_info.get("pid", 0)
                if filter_proc(custom_proc_info):
                    continue
                if len(proc_info['connections']) == 0:
                    continue
                for connections in proc_info['connections']:
                    all_port.append(connections.laddr[1])
                all_port = list(set(all_port))

                # logger.info("parsing process: {}...".format(custom_proc_info['name']))
                custom_proc_info['ppid'] = proc_info.get("ppid", 0)
                custom_proc_info['status'] = proc_info.get("status", 0)
                custom_proc_info['username'] = proc_info.get("username", "Unknown")
                custom_proc_info['cmdline'] = ":".join(
                    proc_info.get("cmdline", ["Unknown", "Unknown"])) if proc_info.get("cmdline") else "Unknown:Unknow"
                custom_proc_info['port_connections'] = len(proc_info['connections'])
                custom_proc_info['memory'] = round(proc_info.get("memory_percent"), 2) if proc_info.get(
                    "memory_percent", 0) else 0.0
                custom_proc_info['listen_port'] = all_port
                try:
                    custom_proc_info['cpu'] = proc.cpu_percent(interval=1)
                except:
                    custom_proc_info['cpu'] = round(proc_info.get("cpu_percent"), 2) if proc_info.get("cpu_percent",
                                                                                                      0) else 0.0
                # logger.debug(custom_proc_info)
            except Exception as e:
                # logger.error("deal error: {} proc_info: {}".format(e, proc_info))
                continue

            custom_procs_info.append(custom_proc_info)
        except OSError as e:
            # logger.error(e)
            continue
    # logger.info("get procs info length: {}".format(len(custom_procs_info)))
    return custom_procs_info


def post_data(data):
    headers = {
        'host': 'cmdb_resource.easyops-only.com',
        'content-type': 'application/json',
        'user': 'easyops',
        'org': '9070'
    }
    url = 'http://' + '192.168.28.28' + '/object/{0}/instance/_import'.format('APP_RESULT')
    try:
        r = requests.request(method='post', url=url, headers=headers, json=data)
        if r.status_code == 200:
            js = r.json()
            if int(js['code']) == 0:
                print js
            else:
                logger.error('Error: %s' % js)
        else:
            logger.error('Error: %s, %s' % (url, r.text))
    except Exception as e:
        print e


if __name__ == "__main__":
    ret = []
    final_proc_info = collect_process_info()
    # for i in range(len(names)):
    # ret.extend(search_name(names[i], final_proc_info))
    for i in range(len(ports)):
        ret.extend(search_port(ports[i], final_proc_info))
    data_list = []
    for proc_info in ret:
        if len(proc_info) != 0:
            data_list.append({"ip": EASYOPS_LOCAL_IP,
                              "pid": str(proc_info.get("pid")),
                              "processname": proc_info.get("name"),
                              "port": proc_info.get("listen_port")[0],
                              "status": str(proc_info.get("status")),
                              "cpu": str(proc_info.get("cpu")),
                              "memory": str(proc_info.get("memory"))})
            put_content_list = "&".join(["{}={}".format(key, value) for key, value in proc_info.items()])

            PutRow("proc_info", put_content_list)

    data = {
        "keys": ["name"],
        "datas": [
            {"name": service, "ret": data_list}
        ]
    }
    post_data(data)