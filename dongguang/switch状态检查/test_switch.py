# -*- coding:utf-8 -*-
import subprocess, os, time, requests, json, threading
from multiprocessing.dummy import Pool as ThreadPool

# 配置信息
easyops_cmdb_host = '192.168.213.213'
easyops_org = '9070'
easy_user = 'easyops'

easy_domain = 'cmdb_resource.easyops-only.com'
headers = {'host': easy_domain, 'org': easyops_org, 'user': easy_user, 'content-Type': 'application/json'}

searchModel = '_SWITCH'

searchParams = {
    "query": {
        "autoCollect": {"$eq": "yes"}
    },
    "fields": {
        "name": True,
        'community': True,
        'ip': True
    }
}

# 最大线程数量
poos_nums = 50
# 命令执行超时时间
cmdTimout = 3

# 保存文件路径 /vagrant/dongguang
path = os.path.dirname(os.path.realpath(__file__))

f_runCmdTimout = open(path + '/runCmdTimout.txt', 'w')


def http_post(method, restful_api, params=None):
    url = u'http://{easy_host}{restful_api}'.format(easy_host=easyops_cmdb_host, restful_api=restful_api)
    if method in ('post', 'POST'):
        try:
            r = requests.post(url, headers=headers, data=json.dumps(params))
            if r.status_code == 200:
                return json.loads(r.content)['data']
        except Exception as e:
            return {"list": []}


# -*- coding: utf-8 -*-
# Easyops搜索实例
class EasyopsPubic(object):

    def search_auto_collect_switch(self):
        """
        公共OID自动搜集，存放在OID.PY文件中
        :return:
        """
        return self.instance_search(searchModel, searchParams)

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
        search_result = http_post(method='post',
                                  restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id),
                                  params=params)

        if not search_result:
            raise Exception('CMDB中没有数据')
        total_instance_nums = int(search_result['total'])

        if total_instance_nums > page_size:
            pages = total_instance_nums / page_size  # total pages = pages + 1
            for cur_page in range(2, pages + 1):
                params['page'] = cur_page

                tmp_result = http_post(
                    restful_api='/object/{object_id}/instance/_search'.format(object_id=object_id), params=params,
                    method='post')
                search_result['list'] += tmp_result['list']

        return search_result['list']


# 搜索实例
def search_datas():
    obj = EasyopsPubic()
    examplelist = obj.search_auto_collect_switch()  # 搜索到所有的实例列表

    if len(examplelist) == 0:
        exit('没有可用的实例')

    aliveexamplelist = []
    # 排除实例列表里没有ip或者团体字的设备
    for example in examplelist:
        # 判断实例的ip和团体字都存在
        if example.has_key('ip') and example.has_key('community'):
            aliveexamplelist.append(example)

    if len(aliveexamplelist) == 0:
        exit('所有实例都没配置好IP和团体字')

    return aliveexamplelist


############################################ 多线程执行命令
class CollectionThread(object):
    def __init__(self):
        """
        :param data: 单个实例ip 团体字信息
        :param oid_name: 配置文件中的oid—name
        """
        self.datas = search_datas()

    # 入口
    def run(self):

        if not self.datas:
            exit('没有搜索到实例.....')

        dataDicts = []  # [{ip:comm}, {ip:comm},]
        # 取单个ip和团体字
        for data in self.datas:
            dataDicts.append({data.get('ip'): data.get('community')})

        self.snmp_run(dataDicts)
        # 关闭线程,
        self.async_pool.close()

    # 拼接执行命令
    def snmp_run(self, dataDicts):
        cmdLists = []
        ipLists = []

        for data in dataDicts:
            # 保存命令
            ip, community = data.keys()[0], data.values()[0]
            cmdLists.append("snmpwalk -v 2c -c {0} {1} 1.3.6.1.2.1.1.5.0".format(community, ip))
            ipLists.append(ip)

        self.async_pool = ThreadPool(poos_nums if len(cmdLists) > poos_nums else len(cmdLists))  # 线程池

        # 执行线程
        results = []
        for index, cmd in enumerate(cmdLists):
            result = self.async_pool.apply_async(self.deal_snmp, args=(cmd, ipLists[index],))
            results.append(result)

        # 执行线程
        for i in results:
            i.wait()  # 等待线程函数执行完毕

    # 执行命令
    def deal_snmp(self, cmd, ip):
        """
        :param cmd: 单条命令
        :param name: oid名字
        :return:
        """
        res = self._run_command(cmd, ip)
        if res:
            print res

    def _run_command(self, cmd, ip, timeout=cmdTimout):
        """执行命令cmd，返回命令输出的内容。
        如果超时将会抛出TimeoutError异常。
        cmd - 要执行的命令
        timeout - 最长等待时间，单位：秒
        """
        # t = threading.currentThread()
        p = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
        t_beginning = time.time()
        while True:
            if p.poll() is not None:
                break
            seconds_passed = time.time() - t_beginning
            if timeout and seconds_passed > timeout:
                # 记录超时的机器ip
                f_runCmdTimout.write(ip + '\n')
                return ''
            time.sleep(0.1)

        if 'Timeout' in p.stdout.read():
            f_runCmdTimout.write(ip + '\n')
        return p.stdout.read()


if __name__ == '__main__':
    CollectionThread().run()
    f_runCmdTimout.close()
