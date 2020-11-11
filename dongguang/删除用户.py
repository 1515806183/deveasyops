# -*- coding:utf-8 -*-
import requests


def delete_user(user):
    url = "http://192.168.213.213:8111/admin/users/@username"
    payload = {
        "username": user
    }
    headers = {
        'host': '',
        'org': '9070',
        'user': 'easyops',
        'Content-Type': 'application/json'
    }

    response = requests.request("DELETE", url, headers=headers, json=payload)
    print(response.text.encode('utf8'))


users_list = users.split(" ")
print users_list
for i in users_list:
    delete_user(i)