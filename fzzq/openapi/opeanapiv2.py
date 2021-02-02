# encoding: utf-8
'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: opeanapiv2.py
@time: 2021/1/7 11:35
@desc:
'''
# -*- coding:utf-8 -*-
import sys
import os
import time
import urllib
import urllib2
import json
import hashlib
import hmac
import traceback
import base64


def do_http(method, url, params={}, headers={}, timeout=60, keys={}):
    """
    do http request
    """
    if not url.startswith('http://'):
        url = 'http://' + url
    method = method.upper()
    # if not isinstance(params, dict) or not isinstance(headers, dict):
    #     raise Exception('params and headers must be dict')
    if len(keys) > 0:
        if method == 'GET':
            params.update(keys)
            data = urllib.urlencode(params)
        else:
            data = urllib.urlencode(keys)
        if '?' not in url:
            url = '%s?%s' % (url, data)
        else:
            url = '%s&%s' % (url, data)
        if method == 'GET':
            request = urllib2.Request(url)
        else:
            if headers.get('Content-Type', '').lower() == 'application/json':
                data = json.dumps(params)
            else:
                data = urllib.urlencode(params)
            request = urllib2.Request(url, data=data)
    else:
        request = urllib2.Request(url)
    for key, val in headers.items():
        request.add_header(key, val)
    request.get_method = lambda: method
    response = urllib2.urlopen(request, timeout=timeout)
    print response.geturl()
    data = response.read()
    response.close()
    return data


def do_api_request(method, url, params={}, headers={}, timeout=30, keys={}):
    headers.setdefault('Content-Type', 'application/json')
    try:
        data = do_http(method, url, params, headers, timeout, keys)
    except urllib2.HTTPError, e:
        print e.geturl()
        print 'http error: ', e.code
        data = e.read()
        # print data
    except urllib2.URLError, e:
        print url
        print e.reason
        raise e
    try:
        return json.loads(data)
    except ValueError, e:
        print 'return data is not json'
        print data
        raise e


def gen_signature(access_key, secret_key, request_time, method, uri, data={}, content_type='application/json'):
    """计算签名"""
    if method == 'GET':
        url_params = ''.join(['%s%s' % (key, data[key]) for key in sorted(data.keys())])
    else:
        url_params = ''
    if method == 'POST' or method == 'PUT':
        m = hashlib.md5()
        m.update(json.dumps(data).encode('utf-8'))
        body_content = m.hexdigest()
    else:
        body_content = ''

    str_sign = '\n'.join([
        method,
        uri,
        url_params,
        content_type,
        body_content,
        str(request_time),
        access_key
    ])
    signature = hmac.new(secret_key, str_sign, hashlib.sha1).hexdigest()

    return signature


def do_api(method, uri, data=None):
    if data is None:
        data = {}
    method = method.upper()
    global ACCESS_KEY, SECRET_KEY, OPEN_API_SERVER
    access_key = ACCESS_KEY
    secret_key = SECRET_KEY

    request_time = int(time.time())
    url = '%s%s' % (OPEN_API_SERVER, uri)
    headers = {
        'host': 'openapi.easyops-only.com',
        'Content-Type': 'application/json',
    }
    signature = gen_signature(
        access_key=access_key,
        secret_key=secret_key,
        request_time=request_time,
        method=method,
        uri=uri,
        data=data,
        content_type=headers.get('Content-Type')
    )

    keys = {
        "accesskey": access_key,
        "signature": signature,
        "expires": str(request_time)
    }

    return do_api_request(method, url, data, headers, keys=keys)


if __name__ == '__main__':
    # 请根据现场情况修改如下配置：
    OPEN_API_SERVER = '10.163.128.232'
    ACCESS_KEY = 'bd248944d1cff9f1c1a6f994'
    SECRET_KEY = '504b44455045577449766870434d586a71484a4d4c65686b766466557562784b'

    # 搜索主机信息
    print do_api('GET', '/dc_console/api/v1/collector/list/host?ip=10.163.131.12&page_size=1&__select__=host.cpu.used_total%2Chost.mem.percent%2Chost.disk.max_used_percent')

    # # 修改主机信息
    # print do_api('PUT', '/cmdbservice/object/HOST/instance/5af7b4da0c812', {
    #     'memo': "hello"
    # })
