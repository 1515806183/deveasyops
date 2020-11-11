#! /usr/local/easyops/python/bin/python
# -*- coding: utf-8 -*-
import os
import json
import requests
import time
import logging

# 注意修改
SETTING = {
    'appkey': 'dingw6wuazsqsbrdldsq',
    'appsecret': 'crqMd87kV-kmoEmmHz_u2qT_suBNQGL9Plv_C5shWoPVep5SHRXZeldfcUzAP2HB',
    'agentid': '862253462',
}


def read_token():
    if os.path.isfile('./dingding_token'):
        with open('./dingding_token', 'r') as fp:
            SETTING['token'] = fp.read()
    else:
        SETTING['token'] = ''


# 先获取最新的token
read_token()


def write_token(token):
    with open('./dingding_token', 'w') as fp:
        fp.write(token)


def get_token(f):
    def _deco(*args, **kwargs):
        result = f(*args, **kwargs)
        if result.get('errcode') in [88, 40001, 40014, 40089]:
            url = "https://oapi.dingtalk.com/gettoken?appkey=%s&appsecret=%s" % (
                SETTING['appkey'], SETTING['appsecret'])
            resp = requests.get(url)
            data = resp.json()
            SETTING['token'] = data['access_token']
            write_token(SETTING['token'])
            result = f(*args, **kwargs)
        return result

    return _deco


@get_token
def list_party():
    url = "https://oapi.dingtalk.com/department/list?access_token=%s" % SETTING['token']
    resp = requests.get(url)
    data = resp.json()
    return data


@get_token
def list_party_user_id(party_id='119146305'):
    url = "https://oapi.dingtalk.com/user/getDeptMember"
    resp = requests.get(url, params={
        "access_token": SETTING['token'],
        "deptId": party_id
    })
    data = resp.json()
    return data


@get_token
def list_party_user(party_id='119146305'):
    url = "https://oapi.dingtalk.com/user/listbypage"
    resp = requests.get(url, params={
        "access_token": SETTING['token'],
        "department_id": party_id,
        "offset": 0,
        "size": 100
    })
    data = resp.json()
    return data


@get_token
def get_user(user_id="382153101280125"):
    url = "https://oapi.dingtalk.com/user/get?access_token=%s&userid=%s" % (
        SETTING['token'], user_id)
    resp = requests.get(url)
    data = resp.json()
    return data


@get_token
def send_msg(msg, touser=["382153101280125"], toparty=[]):
    """可同时发送人和部门，注意：部门不是聊天组"""
    data = {
        "userid_list": ','.join(touser),
        "agent_id": SETTING['agentid'],
        "msg": {
            "msgtype": "text",
            "text": {
                "content": msg
            }
        }
    }
    url = "https://oapi.dingtalk.com/topapi/message/corpconversation/asyncsend_v2?access_token=%s" % SETTING['token']
    resp = requests.post(url, json=data)
    data = resp.json()
    if not data.get('task_id'):
        return data
    task_id = resp.json()['task_id']
    for i in range(3):
        time.sleep(1)
        url = "https://oapi.dingtalk.com/topapi/message/corpconversation/getsendprogress?access_token=%s" % SETTING[
            'token']
        resp = requests.post(url, json={"agent_id": SETTING["agentid"], "task_id": task_id})
        data = resp.json()
        if data['progress']['status'] == 2:
            break
    return data


def get_all_user():
    users = []
    for item in list_party()["department"]:
        party_users = list_party_user(item["id"])["userlist"]
        for user in party_users:
            users.append({
                'name': user['name'],
                'userid': user['userid'],
                'email': user.get('email', ''),
                'active': user['active'],
                'avatar': user['avatar']
            })
    return users


def run(msg_data, users, cmdb_object_key='user_email', **kwargs):
    userids = []
    for user_name, information in users.iteritems():
        userids.append(information[cmdb_object_key])
    logging.info('will send msg to dingding user %s' % (','.join(userids)))
    ret = send_msg(msg=msg_data.get('content'), touser=userids)
    logging.info(u'user: {}, send result: {}'.format(userids, ret))
    return userids


if __name__ == '__main__':
    # print json.dumps(list_party())
    # users = get_all_user()
    print send_msg(msg='hello world')
    # print get_user()