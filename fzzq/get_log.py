#! /usr/local/easyops/python/bin/python
# -*- coding: utf-8 -*-
# 应用发布历史统计脚本

import time
import json
import requests
from datetime import datetime, timedelta

# -------------------------------------------------
# 应用发布统计
DEPLOY_DASHBOARD_OBJECT_ID = 'DEPLOY_DASHBOARD'
# -------------------------------------------------
DEBUG = False
if DEBUG:
    EASYOPS_ORG = 8888
    EASYOPS_USER = "easyops"
    EASYOPS_NOTIFY_HOST = "192.168.100.162:8069"
    EASYOPS_EASYFLOW_HOST = "192.168.100.162:8061"
    EASYOPS_CMDB_HOST = "192.168.100.162:80"
    statistics_days = 10

http_headers = {
    'org': str(EASYOPS_ORG),
    'user': EASYOPS_USER
}


class HTTPRequestException(Exception):

    def __init__(self, message):
        self.message = message
        super(HTTPRequestException, self).__init__(message)


class ResponseTextFormatException(HTTPRequestException):

    def __init__(self):
        message = u'The format of response text is not JSON.'
        super(ResponseTextFormatException, self).__init__(message)


class ResponseCodeException(HTTPRequestException):

    def __init__(self, response_code):
        self.response_code = response_code
        message = u'The response code is {response_code}.'.format(response_code=response_code)
        super(ResponseCodeException, self).__init__(message)


class StatusCodeException(HTTPRequestException):

    def __init__(self, status_code):
        self.status_code = status_code
        message = u'The status code is {status_code}.'.format(status_code=status_code)
        super(StatusCodeException, self).__init__(message)


def http_request(method, host, uri, headers, **kwargs):
    url = u'http://{host}{uri}'.format(host=host, uri=uri)
    response = requests.request(method, url, headers=headers, **kwargs)
    if response.status_code == 200:
        try:
            response_json = json.loads(response.text)
        except ValueError:
            print url
            print ResponseTextFormatException()
            return False
        if response_json['code'] == 0:
            return response_json['data']
        else:
            print url
            print ResponseCodeException(response_json['code'])
            return False
    else:
        print url
        print StatusCodeException(response.status_code)
        return False


# 从notify查询历史部署记录, 按天查询统计, notify pageSize 最大3000, statistics_days 从几天前开始统计截止到今天
def get_deploy_data_from_notify():
    for day in range(0, statistics_days):
        start_time = datetime.strftime(datetime.now() - timedelta(day), '%Y-%m-%d') + " 00:00:00"
        end_time = datetime.strftime(datetime.now() - timedelta(day), '%Y-%m-%d') + " 23:59:59"

        page = 1
        uri = '/operation/log?system=deploy&page={page}&pageSize=2000&start_time={start_time}&end_time={end_time}&app_id={app_id}'.format(
            page=page, start_time=start_time, end_time=end_time, app_id='5e0d95e1b50b6')

        while True:
            response_data = http_request(
                method="GET",
                host=EASYOPS_NOTIFY_HOST,
                uri=uri,
                headers=http_headers
            )
            if not response_data:
                continue

            result_list = response_data['list']
            # print result_list

            # 查询一批数据处理一批数据
            if len(result_list) == 0:
                break
            report_data(result_list, start_time)

            if ((page + 1) * 2000) < response_data['total']:
                page += 1
                uri = '/operation/log?system=deploy&page={page}&pageSize=2000&start_time={start_time}&end_time={end_time}'.format(
                    page=page, start_time=start_time, end_time=end_time)
            else:
                break


def init_deploy_data():
    cluster_info_list = []
    for cluster_type in ["0", '1', '2', '3']:
        count_data = {}
        count_data.setdefault('clusterType', cluster_type)
        count_data.setdefault('deployManualCount', 0)
        count_data.setdefault('deployStrategyCount', 0)
        count_data.setdefault('successCount', 0)
        count_data.setdefault('runningCount', 0)
        count_data.setdefault('failedCount', 0)
        count_data.setdefault('deployCount', 0)
        count_data.setdefault('timeConsume', 0)
        cluster_info_list.append(count_data)
    return cluster_info_list


# 过滤出需要统计的数据
def parse_deploy_data(deploy_list):
    deploy_data = {}
    for item in deploy_list:
        # 只统计手动部署 和 策略部署
        if item['topic'] not in ['instance.deployStrategy', 'instance.deploy']:
            continue
        app_id = item['app_id']
        # 测试时遇到脏数据
        if app_id == '':
            continue
        deploy_data.setdefault(app_id, {})
        deploy_data[app_id]['name'] = deploy_data[app_id].setdefault('name',
                                                                     datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
        deploy_data[app_id]['appInstanceId'] = deploy_data[app_id].setdefault('appInstanceId', app_id)

        deploy_date = time.strftime('%Y-%m-%d 00:00:01', time.localtime(item.get('ctime')))
        deploy_data[app_id]['time'] = deploy_data[app_id].setdefault('time', deploy_date)
        cluster_info_list = init_deploy_data()
        deploy_data[app_id]['clusterInfoList'] = deploy_data[app_id].get('clusterInfoList', cluster_info_list)

        # 按集群分类处理
        task_id = item['event_id']
        task_info = get_task_info(task_id)
        if not task_info:
            continue
        cluster_type = task_info['targetList'][0]['cluster'].get('type')
        if cluster_type is None:
            continue
        deploy_data[app_id]['clusterInfoList'] = handle_cluster_data(cluster_type, item,
                                                                     deploy_data[app_id]['clusterInfoList'])
    return deploy_data


def handle_cluster_data(cluster_type, task_info, cluster_info_list):
    for info in cluster_info_list:
        if info['clusterType'] == cluster_type:
            info['deployCount'] = info.get('deployCount', 0) + 1
            if task_info['topic'] == 'instance.deploy':
                info['deployManualCount'] = info.get('deployManualCount', 0) + 1
            else:
                info['deployStrategyCount'] = info.get('deployStrategyCount', 0) + 1

            if task_info['status'] == 'ok':
                info['successCount'] = info.get('successCount', 0) + 1
            elif task_info['status'] == 'run':
                info['runningCount'] = info.get('runningCount', 0) + 1
            else:
                info['failedCount'] = info.get('failedCount', 0) + 1

            time_consume = task_info['mtime'] - task_info['ctime']
            info['timeConsume'] = (info.get('timeConsume', 0) + time_consume) / info['deployCount']
    return cluster_info_list


def get_task_info(task_id):
    uri = "/deployTask/{task_id}".format(task_id=task_id)
    response_data = http_request(
        method="GET",
        host=EASYOPS_EASYFLOW_HOST,
        uri=uri,
        headers=http_headers
    )
    return response_data


def import_cmdb(import_data):
    uri = "/object/DEPLOY_DASHBOARD/instance/_import"
    http_headers.setdefault('host', 'cmdb_resource.easyops-only.com')
    kwargs = {'data': import_data}
    response_data = http_request(
        method="POST",
        host=EASYOPS_CMDB_HOST,
        uri=uri,
        headers=http_headers,
        **kwargs
    )
    return response_data


def report_data(deploy_list, deploy_date):
    report_data = []
    deploy_data = parse_deploy_data(deploy_list)
    for item in deploy_data.values():
        report_data.append(item)

    # 添加一条默认实例数据记录最新的自动采集时间,前端展示数据时使用
    report_data.append({
        'name': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),  # 当前采集时间
        "appInstanceId": "abcdef0123456",  # appInstanceId 固定
        "time": deploy_date  # 实际部署日期
    })
    import_data = {
        "keys": ["appInstanceId", "time"],
        "datas": report_data
    }
    import_result = import_cmdb(json.dumps(import_data))
    print r'导入cmdb_resource返回结果:'
    print json.dumps(import_result)


if __name__ == '__main__':
    get_deploy_data_from_notify()
