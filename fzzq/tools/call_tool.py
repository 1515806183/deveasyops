# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: 调用工具.py
@time: 2021/1/15 18:04
@desc:
'''
import time
import json
import logging
import requests

SERVER_IP = "10.163.128.232"
TOOLID = 'fa82a4466e65a013662cb05ab1ea132b'  # 工具库ID
VID = 'c3109a853602e6b58a1cfa9cc0051be9'  # 工具库版本ID
EXEC_USER = 'root'  # 执行账户
TIME_RESULT = 10  # 获取工具库执行结果的时间间隔

tool_headers = {
    "host": "tool.easyops-only.com",
    "user": "easyops",
    "org": "3087",
    "content-type": "application/json"
}


class Utils:
    @classmethod
    def post_requests(cls, url, headers, data=None):
        if data:
            cmdb_data = requests.post(url=url, headers=headers, data=json.dumps(data))
            status_code = cmdb_data.status_code
            if status_code == 200:
                return cmdb_data.json()
            if status_code == 500:
                logging.warning('请求url - %s - %s - 请求参数 - %s - 警告 - %s' % (url, status_code, data, cmdb_data.json()))
                return False
            else:
                logging.error('请求url - %s - %s - 请求参数 - %s' % (url, status_code, data))
                return False
        else:
            cmdb_data = requests.post(url=url, headers=headers)
            status_code = cmdb_data.status_code
            if status_code == 200:
                return cmdb_data.json()
            else:
                logging.error('请求url - %s - %s - 请求参数 - %s' % (url, status_code, data))
                return False

    @classmethod
    def get_requests(cls, url, headers):
        cmdb_data = requests.get(url=url, headers=headers)
        status_code = cmdb_data.status_code
        if status_code == 200:
            return cmdb_data.json()
        else:
            logging.error('请求url - %s - %s' % (url, status_code))
            return False


class ToolLibrary:
    @classmethod
    def tool_exec(cls, target_ip):
        params = {
            "toolId": TOOLID,
            "inputs": {
                "@agents": [
                    {
                        "ip": target_ip,
                    }
                ],
            },
            "execUser": EXEC_USER,
            "vId": VID
        }

        url = 'http://{0}/tools/execution'.format(SERVER_IP)
        return Utils.post_requests(url, tool_headers, params)

    @classmethod
    def get_tool_exec_result(cls, execid):
        url = 'http://{0}/tools/execution/{1}'.format(SERVER_IP, execid)
        return Utils.get_requests(url, tool_headers)


def tool_exec(target_ip):
    """执行工具
    :return: 返回代理IP和执行ID
    """

    try:
        result = ToolLibrary.tool_exec(target_ip)
        code = result.get('code')
        if code == 0:
            data = result.get('data')
            exec_id = data.get('execId')  # 任务ID
            if exec_id:
                logging.info('在%s服务器%s执行ip检测工具 - 完成')
                return exec_id
        else:
            logging.warning('在%s服务器%s执行ip检测工具 - 失败')
    except Exception:
        logging.warning('实例IP检测工具执行失败,可尝试将工具标记为生产后重试')


def get_tool_exec_result(exec_id):
    """得到工具执行结果
    :param proxy_ip: 代理IP
    :param exec_id: 执行ID
    :return:
    """
    result = ToolLibrary.get_tool_exec_result(exec_id)
    code = result.get('code')
    if code == 0:
        data = result.get('data')
        if str(data.get('error')) != 'success':
            logging.error('执行下载程序包失败')
            return False
        tableData = data.get('tableData')['default'][0]
        msg = data.get('msg')
        # {u'default': [{u'PKG_VERSION': u'4.0.5.0', u'_E_TS': u'1610615281649637658', u'UPLOAD_FILE': u'/opt/packages/2021-01-14_17_07_59/deploy-product.tar.gz'}]}
        logging.info('tableData info: %s' % tableData)
        return tableData, msg
    else:
        # 获取执行结果失败
        logging.error('获取ip检测工具执行结果失败 - ', result)
        return False, False


def main(target_ip):
    exec_id = tool_exec(target_ip)  # 执行工具库中的工具
    logging.info('exec_id : %s' % exec_id)
    time.sleep(TIME_RESULT)  # 等待工具执行完成（需预估工具所执行完成的时间）
    ret, msg = get_tool_exec_result(exec_id)  # 获取工具的执行结果
    if ret:
        PKG_VERSION = ret['PKG_VERSION']
        UPLOAD_FILE = ret['UPLOAD_FILE']
        return {"PKG_VERSION": PKG_VERSION, "UPLOAD_FILE": UPLOAD_FILE}, msg

    return False, False


if __name__ == '__main__':
    ret, msg = main(SERVER_IP)
