# -*- coding: utf-8 -*-
import subprocess, platform, json, re, requests

easyops_cmdb_host = '192.168.28.28'
easyops_org = '9070'
easy_user = 'easyops'
# header配置
easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

sys_type = 'type'  # 物理机or虚拟机
sys_sn = 'sn'  # 序列号
hostuuid = 'hostuuid'  # uuid

data = {
    "dims": {
        "pks": ['ip'],
        "object_id": "HOST"
    },
    "vals": {
        "ip": '192.168.28.28',
        sys_type: '物理机'
    }
}

os_type = platform.system()


def run():
    if os_type == 'Linux':
        # 序列号, 如果是虚拟机，则VMware开头
        sn_cmd = r"dmidecode -s system-serial-number"
        sn_result = subprocess.check_output(sn_cmd, shell=True)
        sn_res = sn_result.decode("unicode_escape")

        if 'VMware' in sn_res:
            # 表示类型为虚拟机，没有序列号
            data.get('vals')[sys_type] = '虚拟机'
            # VMware-56 4d 3d 7f 39 00 e9 33-29 6a 7e 64 63 65 3b fc
            sn_res = sn_res.lower().split('-')
            one = sn_res[1].split(' ')
            one = ''.join(one[:4]) + '-' + ''.join(one[4: 6]) + '-' + ''.join(one[-2:])
            two = sn_res[-1].split(' ')
            two = ''.join(two[:2]) + '-' + ''.join(two[2:])
            uuid = one + '-' + two
            uuid = uuid.split('\n')[0]
            data.get('vals')[hostuuid] = uuid
            data.get('vals')[sys_sn] = ''
        elif '-' in sn_res:
            data.get('vals')[sys_type] = '虚拟机'
            data.get('vals')[hostuuid] = sn_res.split('\n')[0]
            data.get('vals')[sys_sn] = ''
        else:
            # 默认是物理机，无需修改属性值,只要更新序列号
            if sys_sn:
                data.get('vals')[sys_sn] = sn_res.split('\n')[0]
                data.get('vals')[hostuuid] = ''

    else:
        cmd = 'wmic CSPRODUCT list full'
        res = subprocess.check_output(cmd, shell=True)
        sn_res = re.search('IdentifyingNumber=(.*)', res)
        try:
            sn_res = sn_res.group(1)
        except Exception:
            sn_res = ''

        if 'VMware' in sn_res:
            # 表示类型为虚拟机，没有序列号
            data.get('vals')[sys_type] = '虚拟机'
            # VMware-56 4d 3d 7f 39 00 e9 33-29 6a 7e 64 63 65 3b fc
            sn_res = sn_res.lower().split('-')
            one = sn_res[1].split(' ')
            one = ''.join(one[:4]) + '-' + ''.join(one[4: 6]) + '-' + ''.join(one[-2:])
            two = sn_res[-1].split(' ')
            two = ''.join(two[:2]) + '-' + ''.join(two[2:])
            uuid = one + '-' + two
            uuid = uuid.split('\r\r')[0]
            data.get('vals')[hostuuid] = uuid
            data.get('vals')[sys_sn] = ''
        elif '-' in sn_res:
            data.get('vals')[sys_type] = '虚拟机'
            data.get('vals')[hostuuid] = sn_res.split('\n')[0]
            data.get('vals')[sys_sn] = ''

        else:
            SKUNumber = re.search('IdentifyingNumber=(.*)', res)
            try:
                sn = SKUNumber.group(1)
            except Exception:
                sn = ''
            if sn:
                data.get('vals')[sys_sn] = sn.split('\r\r')[0]
                data.get('vals')[hostuuid] = ''

    ip = data['vals'].get('ip')
    obj = EasyopsPubic(ip)
    host_instanceId = obj()[0].get('instanceId')

    url = "/object/{0}/instance/{1}".format('HOST', host_instanceId)
    res = obj.http_post('put', url, data['vals'])
    if res == 0:
        print '采集成功：%s' % data


# Easyops查询实例
class EasyopsPubic(object):
    def __init__(self, ip):
        self.ip = ip

    def __call__(self, *args, **kwargs):
        return self.search_auto_collect_switch()

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        parmas = {
            "query": {"ip": self.ip},
            "fields": {
                "name": True
            }
        }
        return self.instance_search('HOST', parmas)

    # 搜索实例
    def instance_search(self, object_id, params):
        """
        :param object_id: 配置文件中的搜索模型ID
        :param params: 配置文件中的搜索查询条件
        :return:
        """
        if params.has_key('page_size'):
            page_size = 500
        else:
            page_size = 1000
        params['page_size'] = page_size
        params['page'] = 1
        search_result = self.http_post(method='post',
                                       restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                       params=params)
        if not search_result:
            exit('没有查询到数据')

        total_instance_nums = int(search_result['total'])

        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 1):
                params['page'] = cur_page

                tmp_result = self.http_post(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id), params=params,
                    method='post')
                search_result['list'] += tmp_result['list']

        return search_result['list']

    # 请求cmdb，汇报数据
    def http_post(self, method, restful_api, params=None):
        url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
        if method in ('post', 'POST'):
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('put', "PUT"):
            try:

                r = requests.put(url=url, headers=headers, json=params)
                if r.status_code == 200:
                    return json.loads(r.content)['code']
            except Exception as e:
                return {"list": []}

        elif method in ('get', 'get'):
            try:
                r = requests.get(url, headers=headers)
                if r.status_code == 200:
                    return json.loads(r.content)['data']
            except Exception as e:
                return {"list": []}

        elif method in ('many_post', "many_POST"):
            try:
                url = 'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
                r = requests.post(url=url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    return json.loads(r.content)
            except Exception as e:
                print e
                return {"list": []}

        elif method in ("info_port",):
            # 这里是交换机端口关联，因为关联成功返回的信息{u'message': u'', u'code': 0, u'data': None, u'error': u''}， 如果像上面那么写 data返回的是None
            try:
                r = requests.post(url, headers=headers, data=json.dumps(params))
                if r.status_code == 200:
                    data = json.loads(r.content)
                    if data.get('code') == 0:
                        return r.content
                    else:
                        return False
            except Exception as e:
                return False


if __name__ == '__main__':
    run()
