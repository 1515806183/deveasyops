# -*- coding:utf-8 -*-
import requests, json, time

DEPLOY_SUMMARY = json.loads(DEPLOY_SUMMARY)

total = DEPLOY_SUMMARY.get('total')
success = DEPLOY_SUMMARY.get('success')

online_date = int(time.mktime(time.strptime(online_date, '%Y-%m-%d %H:%M:%S')))
params = {
    "online_id": online_id,
    "version": version,
    "state": 0,
    "operator": operator,
    "online_date": online_date,
    "application": application,
    "business": business
}

if total == success:
    pass
else:
    params['state'] = 1

url = "http://100.116.9.94:28080/online/result"

headers = {'content-Type': 'application/json'}
r = requests.post(url, data=json.dumps(params), timeout=30)

print r.content
