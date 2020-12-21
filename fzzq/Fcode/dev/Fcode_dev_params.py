# coding:utf-8
import requests, json, time, logging

# 0开发， 1 测试 2 生产
clusterType = '0'

APP_NAME = "secured_ifc-index-dubbo-service"

cmdb_host = '28.163.0.123'
easyops_org = '3087'
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

params = {
    "query": {
        "name": {
            "$eq": APP_NAME
        }
    },
    "fields": {
        "instanceId": True

    }
}

logging.info('search app params: %s' % params)

url = "http://" + cmdb_host + "/object/APP/instance/_search"

logging.info('search app url: %s' % url)

r = requests.post(url, data=json.dumps(params), headers=headers, timeout=30)

data = json.loads(r.content)['data']['list'][0]

logging.info('search app ret_data: %s' % data)

try:
    app_instanceId = data.get('instanceId')
    logging.info('search app app_instanceId: %s' % app_instanceId)
    url = "http://" + cmdb_host + ":8061/deployStrategy?appId=" + app_instanceId
    logging.info('search app deployStrategy url : %s' % url)

    payload = {}
    headers = {
        'host': 'deploy.easyops-only.com',
        'org': easyops_org,
        'user': easy_user,
        'content-Type': 'application/json',
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    data_list = json.loads(response.text.encode('utf8')).get('data')
    logging.info('search app deployStrategy data_list : %s' % data_list)

    for data in data_list:
        cluster_type = str(data.get('clusterType'))
        if cluster_type == clusterType:
            name = data.get('name')
            id = data.get('id')
            if u'全量部署' == name:
                logging.info('search app package all id : %s' % id)
                PutStr("all_id", id)
            elif u'灰度1台机器部署' == name:
                logging.info('search app package  one_id : %s' % id)
                PutStr("one_id", id)
            elif u'灰度其他机器部署' == name:
                logging.info('search app package  other_id : %s' % id)
                PutStr("other_id", id)

except Exception as e:
    logging.error(str(e))
    raise Exception('先创建部署策略')

PutStr("version", version)  # 部署版本
PutStr("application", APP_NAME) # 应用名称
PutStr("ftp_file_url", ftp_url) # ftp下载地址
