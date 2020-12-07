# coding:utf-8
import requests, json, time

easyops_org = '3087'
easy_user = 'defaultUser'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

params = {
    "query": {
        "APP.name": {
            "$eq": "secured_ifc-index-dubbo-service"
        }

    },
    "fields": {
        "business": True,
        "ftp_url": True,
        "operator": True,
        "version": True,
        "online_date": True,
        "name": True,

    }
}

url = "http://28.163.0.123/object/FCODE_FLOW/instance/_search"


r = requests.post(url, data=json.dumps(params), headers=headers, timeout=30)

data = json.loads(r.content)['data']['list'][0]
PutStr("online_id", data.get('online_id'))
PutStr("version", data.get('version'))
PutStr("operator", data.get('operator'))
PutStr("online_date", data.get('online_date'))
PutStr("application", application)
PutStr("business", data.get('business'))
PutStr("ftp_url", data.get('ftp_url'))
