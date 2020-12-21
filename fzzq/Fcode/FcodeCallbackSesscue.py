# -*- coding:utf-8 -*-
import requests, json, time

# print DEPLOY_SUMMARY
# print online_id
# print version
# print operator
# print online_date
# print application
# print business

online_date = int(time.mktime(time.strptime(online_date, '%Y-%m-%d %H:%M:%S')))
# params = {
#     "online_id": online_id,
#     "version": version,
#     "state": 0,
#     "operator": operator,
#     "online_date": online_date,
#     "application": application,
#     "business": business,
#     "message": "success"
# }


payload = 'online_id={0}&version={1}&state={2}&operator={3}&online_date={4}&application={5}&business={6}&message={7}'.format(
    online_id, version, 0, operator, online_date, application, business, 'success')

url = "http://100.116.9.94:28080/online/result"

headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}
response = requests.request("POST", url, headers=headers, data=payload, timeout=30)

print payload
print "------------------------------"
print response.content
