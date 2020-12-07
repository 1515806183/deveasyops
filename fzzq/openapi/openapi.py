#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import math
import urllib2
import json
import hashlib
import hmac

from urlparse import urlparse

__auther__ = 'Peach'

'''
带签名加密的OpenAPI请求方法
'''


class EasyRequest(object):
    ACCESS_KEY = ''
    SECRET_KEY = ''
    IP = ''

    def __init__(self, headers=None, method=None, url=None, data=None, params=None):
        if headers is None:
            headers = {}
        if method is None:
            method = ''
        if url is None:
            url = ''
        if data is None:
            data = {}
        if params is None:
            params = {}

        self.headers = headers
        self.__method = method
        self.__url = url
        self.__data = data
        self.params = params
        self.signature_params = {}

        self.set_header('Host', 'openapi.easyops-only.com')

    def set_header(self, key, value):
        self.headers[key] = value
        return self

    def get_header(self, key):
        if key in self.headers:
            return self.headers[key]
        return None

    @property
    def method(self):
        return self.__method

    @method.setter
    def method(self, method):
        self.__method = method.upper()

    @property
    def url(self):
        return self.__url

    @url.setter
    def url(self, url):
        if url.startswith('/'):
            self.__url = 'http://' + EasyRequest.IP + url
        else:
            self.__url = 'http://' + EasyRequest.IP + '/' + url

    @classmethod
    def is_json(cls, jsondata):
        try:
            json.loads(jsondata)
        except json.JSONDecoder:
            return False
        return True

    @property
    def data(self):
        return self.__data

    @data.setter
    def data(self, body_data):
        """
        设置请求的body
        """
        if self.is_json(body_data):
            self.jsondata = body_data
        else:
            self.__data = body_data
            self.set_header('Content-Type', 'text/plain')

    @property
    def jsondata(self):
        return json.dumps(self.__data)

    @jsondata.setter
    def jsondata(self, jsondata):
        """
        设置json格式的请求body
        """
        if not self.is_json(jsondata):
            raise ValueError("set_json_data failed: argument should be an valid json string")
        self.__data = jsondata
        self.set_header('Content-Type', 'application/json')

    def set_param(self, key, value):
        self.params[key] = value
        return self

    def send(self):

        return EasyCurl.send_request(self.signature(str(math.trunc(time.time()))))

    def __get_url_path(self):
        o = urlparse(self.__url)
        return o.path

    def build_url(self):
        """
        签名，url，参数，组合成完整url
        :return:
        """
        parts = urlparse(self.__url)

        query_string = ''
        param = dict(self.params, **self.signature_params)

        if len(parts.query) > 0:
            query_string += parts.query + '&' + '&'.join(['%s=%s' % (k, v) for k, v in param.items()])
        else:
            query_string += '&'.join(['%s=%s' % (k, v) for k, v in param.items()])

        ret_url = parts.scheme + '://' + parts.netloc

        if len(parts.path) > 0:
            ret_url += parts.path

        if query_string:
            ret_url += '?' + query_string

        return ret_url

    def signature(self, request_time):
        if self.__method == 'POST' or self.__method == 'PUT':
            if '' not in self.headers or self.headers[''] == "" or self.headers[''] is None:
                self.set_header('Content-Type', 'application/json')
            content_type = self.get_header('Content-Type')

        else:
            self.set_header('Content-Type', '')
            self.headers.pop('Content-Type')
            content_type = ''

        url_param = ''.join(['%s%s' % (k, self.params[k]) for k in sorted(self.params.keys())])

        content_md5 = ''
        if self.__method == 'POST' or self.__method == 'PUT':
            md5 = hashlib.md5()
            md5.update(self.__data)
            content_md5 = md5.hexdigest()

        url_path = self.__get_url_path()
        string_to_signaure = "\n".join([
            self.__method,
            url_path,
            url_param,
            content_type,
            content_md5,
            request_time,
            EasyRequest.ACCESS_KEY]
        ).encode()

        s = EasyRequest.SECRET_KEY.encode()
        self.signature_params['accesskey'] = EasyRequest.ACCESS_KEY
        self.signature_params['signature'] = hmac.new(s, string_to_signaure, hashlib.sha1).hexdigest()
        self.signature_params['expires'] = request_time

        return self


class EasyCurl(object):

    @classmethod
    def parse_request(cls, request):
        url_request = urllib2.Request(url=request.build_url(), headers=request.headers)

        if request.method == 'POST' or request.method == 'PUT':
            url_request.data = request.data

        '''Python 2 HTTP请求的特殊处理'''
        if request.method == 'DELETE':
            url_request.get_method = lambda: 'DELETE'
        if request.method == 'PUT':
            url_request.get_method = lambda: 'PUT'

        return url_request

    @classmethod
    def send_request(cls, request):
        req = EasyCurl.parse_request(request)

        try:
            response = urllib2.urlopen(req, timeout=30)
            return EasyResponse(response.getcode(), response.info(), response.read())

        except Exception, e:
            code = -1
            if hasattr(e, 'code'):
                code = e.code
            headers = {}
            if hasattr(e, 'headers'):
                headers = e.headers
            reason = ''
            if hasattr(e, 'read'):
                reason = e.read()

            return EasyResponse(code, headers, reason)


class EasyResponse(object):
    def __init__(self, code, headers, info=''):
        self.code = code
        self.headers = self.parse_headers(headers, info)
        self.info = info

    @classmethod
    def parse_headers(cls, headers, info):
        __headers = {}
        if info == '':
            for key, value in headers.items():
                __headers[key] = value
        else:
            __headers = {}

        return __headers


'''
用例代码
'''


# 打印请求结果
def __test_print_result(request):
    # 发送请求
    result = request.send()

    # 打印请求结果，请求成功时，code = 200
    print result.code

    # 获取请求结果信息，测试URL请求成功时， info = Signature success!
    print result.info
    # print result.headers

    return json.loads(result.info)


# POST方法
def __post(request, url, parse):
    # 设置请求类型
    request.method = 'POST'

    # 设置请求的 url，
    request.url = url

    # 设置请求消息内容，格式举例如下，是纯Json字符串, 也可以是自定义任意文本格式
    # request.data = "aaa,bbb,ccc\n111,222,333" # example_1
    # request.jsondata = "[]"  # example_2
    # request.jsondata = '{"query":{},"fields":{"instanceId":true,"name":true, "permission": true}}'  # example_3
    request.jsondata = json.dumps(parse)

    return __test_print_result(request)


# GET方法
def __get(request, url):
    request.method = 'GET'
    request.url = url

    # 设置请求参数
    # request.set_param('page', 1).set_param('pageSize', 30)

    __test_print_result(request)


# PUT方法
def __put(request, url):
    request.method = 'PUT'
    request.url = url
    # request.data = json.dumps({"id": 123, "name": "jack"})
    __test_print_result(request)


# DELETE方法
def __delete(request, url):
    request.method = 'DELETE'
    request.url = url
    __test_print_result(request)


if __name__ == '__main__':
    # 设置签名用的key

    EasyRequest.ACCESS_KEY = "04463dbea830dd25df7d782f"
    EasyRequest.SECRET_KEY = "6a494f72656a6b584573714b57774679687863427843565a6f6a686470596e4c"
    # 设置请求IP地址
    EasyRequest.IP = "192.168.28.28"
    # 实例化
    request = EasyRequest()

    # 获取 业务系统信息uri: /object/{objectId}/instance/_import
    url = '/cmdb_resource/object/{objectId}/instance/_search'.format(objectId='HOST')  # objectId模型ID
    # url = '/cmdb_resource/object/{objectId}/instance/_import'.format(objectId='Parts')  # objectId模型ID
    # url = '/cmdb_resource/object/{objectId}/instance/5b4ea4ada0a87'.format(objectId='Parts')  # objectId模型ID
    # url = '/cmdb_resource/object/{objectId}/instance/_batch?instanceIds=5b4ea4a4fc216;5b4ea4ada0a87'.format(objectId='Parts')  # objectId模型ID

    print url
    # 参数
    # parse = '{"query":{"name": "研究所"},"fields":{"instanceId":true, "name":true, "_businesses_APP.owner": true, "_businesses_APP.tester": true, "_businesses_APP.name_chineses": true, "_businesses_APP.name": true, "_businesses_APP.instanceId": true},"only_relation_view":true,"only_my_instance":false, "page": 1,"page_size": 2000}'
    # parse = '{"query":{"name": "secured_ifc-index-dubbo-service"},"fields":{"instanceId":true, "name":true, "clusters.deviceList.ip": true, "port": true},"only_relation_view":true,"only_my_instance":false, "page": 1,"page_size": 2000}'
    parse = {
        "fields": {
            "deleteAuthorizers": True,
            "updateAuthorizers": True
        }
    }
    res = __post(request, url, parse)
