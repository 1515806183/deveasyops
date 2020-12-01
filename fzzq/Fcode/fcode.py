# coding:utf-8

import json
from wsgiref.simple_server import make_server
import requests
import logging
import os
import time

FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
path = os.getcwd() + "/log"

if not os.path.exists(path):
    os.makedirs(path)
logging.basicConfig(format=FORMAT,
                    filename='{path}/auto_permison-{date}.log'.format(path=path, date=time.strftime('%Y%m%d')),
                    filemode='a')
logger = logging.getLogger('log')
logger.setLevel(logging.INFO)

headers = {
    "content-Type": "application/json",
    "host": "cmdb_resource.easyops-only.com",
    "org": "3087",
    "user": "defaultUser"
}

easyopsHost = '28.163.0.123'


def http_post(method, url, params=None):
    if method == 'POST':
        r = requests.post(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            ret = json.loads(r.content)['data']
            return ret['list']

    elif method == 'PUT':
        r = requests.put(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            ret = json.loads(r.content)['data']
            return ret

    elif method == 'GET':
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            ret = json.loads(r.content)['data']
            return ret


def DealData(callback, modelID):
    """
    :param callback: 回调信息
    :param modelID: 模型ID
    :return:
    """

    object_id = callback['data']['ext_info']['object_id']  # 模型ID

    if object_id == 'FCODE_FLOW':
        flowId = ''  # 部署策略ID
        focdeId = callback['data']['target_id']  # 流水号ID
        name = callback['data']['ext_info']['instance_name']  # 实例名称流水号
        user = callback['data'].get('operator', 'easyops')

        # 根据focdeId  获取应用名称 /object/@object_id/instance/@instance_id
        app_url = "http://{host}/object/{id}/instance/{model}".format(host=easyopsHost, id=modelID, model=focdeId)
        app_ret = http_post('GET', app_url)
        AppName = app_ret.get('application')  # 应用名

        # 根据应用ID，获取对应的Fcode流程管理ID，拼接URL
        search_url = "http://{host}/object/{model}/instance/_search".format(host=easyopsHost, model='APP')
        print 'search_url: ', search_url
        logging.info('查询{name}应用URL：{url}'.format(name=name, url=search_url))
        search_parse = {
            "query": {
                "name": {
                    "$eq": "{APPNAME}".format(APPNAME=AppName)
                }
            }
        }
        print 'search_parse:', search_parse
        logging.info('查询{name}应用参数：{parse}'.format(name=name, parse=search_parse))
        search_ret = http_post('POST', search_url, search_parse)

        print 'search_ret: ', search_ret
        logging.info('查询应用详情:', search_ret)

        if search_ret:
            piplineList = search_ret[0].get('__pipeline')
            print "piplineList: ", piplineList
            app_instanceId = search_ret[0]['instanceId']
            print "app_instanceId: ", app_instanceId
            logging.info(u'应用部署ID列表:', piplineList)
            print "AppName: ", AppName
            for pip in piplineList:
                pipName = pip.get('name')
                pipID = pip.get('flowId')
                logging.info(u'应用部署名称{name}和ID{id}:'.format(name=pipName, id=pipID))
                fcode_name = 'Fcode_' + AppName
                print u'fcode_name: ', fcode_name
                if pipName == fcode_name:
                    flowId = pipID
                    break
            print flowId
            logging.info(u'应用部署策略ID{id}:'.format(id=flowId))
            if flowId:
                devUrl = 'http://{host}/app/{appid}/pipeline/{flowid}/taskOutputs?page=1'.format(host=easyopsHost,
                                                                                                 appid=app_instanceId,
                                                                                                 flowid=flowId)

                logging.info(u'应用部署devUrl{url}:'.format(url=devUrl))
                print devUrl
                data = {
                    "operator": user,
                    "devUrl": devUrl

                }
                logging.info(u'应用更新的数据:', data)

                url = "http://{host}/object/{model}/instance/{id}".format(host=easyopsHost, model=modelID,
                                                                          id=focdeId)
                print url
                http_post('PUT', url, data)


def application(environ, start_response):
    # 定义文件请求的类型和当前请求成功的code
    try:
        start_response('200 OK', [('Content-Type', 'application/json')])
        # environ是当前请求的所有数据，包括Header和URL，body

        if environ.get("CONTENT_LENGTH") == '':
            return environ
        else:
            request_body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH")))
            callback = json.loads(request_body)

            # 处理数据
            DealData(callback, "FCODE_FLOW")

            return [json.dumps(request_body)]
    except Exception as e:
        pass


if __name__ == "__main__":
    port = 9055
    httpd = make_server(easyopsHost, port, application)
    logger.info("serving http on port {0}...".format(str(port)))
    httpd.serve_forever()
