# -*- coding:utf-8 -*-
import requests, json, time, sys

# print DEPLOY_SUMMARY
# print online_id
# print version
# print operator
# print online_date
# print application
# print business
status_type = int(status_type)

if status_type == 0:
    message = "灰度部署一台失败"
if status_type == 0:
    message = "灰度部署一台失败,并回滚版本号: %s" % callback_version
elif status_type == 2:
    message = "灰度部署其他机器失败"
elif status_type == 3:
    message = "灰度部署其他机器失败, 回滚上一个节点，回滚版本号: %s" % callback_version
elif status_type == 4:
    message = "灰度部署其他机器失败, 全量回滚，回滚版本号: %s" % callback_version
elif status_type == 5:
    message = "全量部署失败"
elif status_type == 6:
    message = "全量部署失败, 全量回滚，回滚版本号: %s" % callback_version
else:
    message = "部署失败"

online_date = int(time.mktime(time.strptime(online_date, '%Y-%m-%d %H:%M:%S')))
# params = {
#     "online_id": online_id,
#     "version": version,
#     "state": 1,
#     "operator": operator,
#     "online_date": online_date,
#     "application": application,
#     "business": business,
#     "message": message
# }

payload = 'online_id={0}&version={1}&state={2}&operator={3}&online_date={4}&application={5}&business={6}&message={7}'.format(
    online_id, version, state, operator, online_date, application, business, message)

headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

url = "http://100.116.9.94:28080/online/result"

response = requests.request("POST", url, headers=headers, data=payload, timeout=30)

print params
print "------------------------------"
print response.content
sys.exit(1)
