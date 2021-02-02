# coding:utf-8
import requests, json, time, logging, sys, IPy

reload(sys)
sys.setdefaultencoding('utf8')

cmdb_host = EASYOPS_CMDB_HOST.split(':')[0]
easyops_org = str(EASYOPS_ORG)
# cmdb_host = "10.163.128.232"
# easyops_org = "3087"
# application = "fcodeTest20201230"
# clusterType = "开发"
# ftp_file_url = 'ftp://qaftp.fzzqft.com/fcode_liusha-test_test-dubbo_release-20201230-1/1/4.0.6.0'

cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}

deploy_headers = {
    'host': 'deploy.easyops-only.com',
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json',
}

version = ftp_file_url.split('/')[-1]
if not version:
    version = ftp_file_url.split('/')[-2]

# pageke_env_type 1为开发，3为测试，15为生产，程序包版本
pageke_env_type = ''
# 集群环境0开发， 1 测试 2 生产
if clusterType == "开发":
    clusterType = "0"
    pageke_env_type = '1'
    version += '-DEV'
elif clusterType == "测试":
    clusterType = '1'
    pageke_env_type = '3'
    version += '-UAT'

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')


def http_post(method, url, params=None, headers=cmdb_headers):
    if method == 'POST':
        r = requests.post(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                ret = json.loads(r.content)['data']
                return ret['list']
            except Exception as e:
                return json.loads(r.content)
        else:
            return json.loads(r.content)

    elif method == 'POSTS':
        try:
            page_size = 100
            params['page'] = 1
            params['page_size'] = page_size
            ret_list = []
            while True:
                r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
                if r.status_code == 200:
                    one_ret = json.loads(r.content)['data']['list']  # 第一次获取的数据

                    if len(one_ret) == 0:
                        break

                    if len(one_ret) <= page_size:
                        params['page'] += 1
                        ret_list += one_ret
                    else:
                        break
            return ret_list
        except Exception as e:
            return []

    elif method == 'PUT':
        r = requests.put(url=url, data=json.dumps(params), headers=headers, timeout=30)
        if r.status_code == 200:
            try:
                ret = json.loads(r.content)['data']
                code = str(json.loads(r.content)['code'])
            except Exception as e:
                ret = json.loads(r.content)
                code = '1'
            return code, ret

    elif method == 'GET':
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            ret = json.loads(r.content)['data']
            return ret

    elif method in ("repo",):
        try:
            r = requests.post(url, headers=headers, data=json.dumps(params), timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                if data.get('code') == 0:
                    return r.content
                else:
                    return False
        except Exception as e:
            return False

    elif method in ('DELETE', 'delete'):
        try:
            r = requests.delete(url, headers=headers, data=json.dumps(params), timeout=60)
            if r.status_code == 200:
                data = json.loads(r.content)
                return data.get('code')
            else:
                return r.content
        except Exception as e:
            return e


class inspectVersion():
    def __init__(self):
        self.run()

    def search_app(self):
        try:
            params = {
                "query": {
                    "name": {
                        "$eq": application
                    }
                },
                "fields": {
                    # "instanceId": True,
                    "clusters.type": True,
                    "clusters.deviceList.ip": True

                }
            }
            url = "http://{HOST}/object/APP/instance/_search".format(HOST=cmdb_host)
            r = requests.post(url, data=json.dumps(params), headers=cmdb_headers, timeout=30)
            self.data = json.loads(r.content)['data']['list'][0]
        except Exception as e:
            logging.info('查询应用信息报错:%s' % e)
            sys.exit(1)

    def search_deploy(self):
        try:
            self.all_id = ''
            self.one_id = ''
            self.other_id = ''
            app_instanceId = self.data.get('instanceId')
            logging.info(u'查询应用的实例ID: %s' % app_instanceId)
            url = "http://{HOST}:8061/deployStrategy?appId={ID}".format(HOST=cmdb_host, ID=app_instanceId)
            logging.info('查询应用的部署策略的url : %s' % url)
            response = requests.request("GET", url, headers=deploy_headers)
            data_list = json.loads(response.text.encode('utf8')).get('data')
            for data in data_list:
                cluster_type = str(data.get('clusterType'))
                if cluster_type == clusterType:
                    logging.info('查询集群的类型为:%s' % str(cluster_type))
                    name = data.get('name')
                    id = data.get('id')
                    if u'全量部署' == name:
                        self.all_id = id
                    elif u'灰度1台机器部署' == name:
                        self.one_id = id
                    elif u'灰度其他机器部署' == name:
                        self.other_id = id
        except Exception as e:
            logging.error(str(e))
        finally:
            logging.info(u'部署策略ID：all_id: %s, one_id: %s, other_id: %s' % (self.all_id, self.one_id, self.other_id))
            if not (self.all_id and self.one_id and self.other_id):
                logging.error(u'请先创建部署策略')
                sys.exit(1)

    # 检查版本， 如果存在，返回True, 程序包版本ID
    def inspect_version(self):

        """
        :param version: 程序包版本，又是程序包名称
        :param commitId: git ID
        :return:
        """

        logging.info('The version of the package lookup : %s' % version)

        params = {
            "query": {
                "name": {"$eq": application},

            },
            "fields": {
                "instanceId": True,
                "_packageList": True
            },
            "only_relation_view": True,
            "only_my_instance": False,
            "page_size": 1
        }
        try:
            url = "http://{HOST}/object/APP/instance/_search".format(HOST=cmdb_host)
            data = http_post('POST', url, params=params)[0]

            packageList = data.get('_packageList')

            if not packageList:
                logging.error(
                    'The application does not have a package. Please create a package first. The package name is the same as the application name')
                exit(1)

            versionId = ''
            for package in packageList:
                packageId = package.get('packageId')  # 程序包ID
                logging.info('Package ID to start lookup: %s' % packageId)

                # 根据packageId 获取所有的程序包

                payload = {}
                version_result = []
                version_page = 1
                while True:
                    url = "http://{host}/version/list?packageId={packageId}&page={page}&pageSize=300".format(
                        packageId=packageId, page=version_page, host=cmdb_host)
                    response = requests.request("GET", url, headers=deploy_headers, data=payload)
                    result = response.json()
                    if result['data']['list'] and len(result['data']['list']) > 0:
                        data_list = result['data']['list']
                        version_result = version_result + data_list
                        version_page += 1
                    else:
                        break

                falg = False  # 标记找到了程序包
                for data in version_result:
                    name = data.get('name')  # 程序包名称
                    commit_id = data.get('memo')  # 备注
                    env_type = str(data.get('env_type'))  # 运行环境。3 测试
                    if (name == version) and (env_type == pageke_env_type):  # 如果版本相同，commitid相同 环境相同则有这个包
                        versionId = data.get('versionId')  # 程序包版本
                        falg = True
                        return True, versionId
                if falg:
                    logging.warning("Found package, version ID of package: %s" % versionId)
                    return True, versionId
                else:
                    return False, False
            else:
                logging.warning('Package not found, new package can be created')
                return False, False

        except Exception as e:
            print e
            raise Exception('获取应用没有程序包出错')

    # 检查开发，测试是否存在生产环境IP
    def checkIp(self):
        try:
            params = {"query": {},
                      "fields": {"name": True}}

            url = "http://{HOST}/object/NonProIpNetwork/instance/_search".format(HOST=cmdb_host)
            ret = http_post('POSTS', url, params)
            Segment_list = [ip.get('name') for ip in ret]
            logging.info('查询的IP网段为：%s' % Segment_list)

            # 循环数据，取集群ip信息
            clusters_info_list = self.data.get('clusters')
            for data in clusters_info_list:
                deviceList = data.get('deviceList')
                cluster_type = data.get('type')
                # 判断集群类型是否相同
                if cluster_type == clusterType:
                    logging.info('集群类型为: %s' % clusterType)
                    logging.info('集群主机列表：%s' % deviceList)
                    all_deviceList = []
                    nonproductive_list = []
                    if deviceList:
                        for device in deviceList:
                            device_ip = str(device.get('ip'))
                            all_deviceList.append(device_ip)
                            # 判断IP是否是生产IP
                            for segment in Segment_list:
                                if device_ip in IPy.IP(segment):
                                    nonproductive_list.append(device_ip)

                    productive_list = list(set(all_deviceList) - set(nonproductive_list))
                    if len(productive_list) > 0:
                        return productive_list
                    else:
                        return []

        except Exception as e:
            logging.error('查询非生产IP网段出错，请添加非生产IP网段')
            sys.exit(1)

    def run(self):
        self.search_app()
        # 开发生产第一步，检查主机是否存在生产IP
        productive_list = self.checkIp()
        self.search_deploy()
        code, PagekeVersionId = self.inspect_version()
        if not PagekeVersionId:
            PagekeVersionId = u'无'

        if code:
            # 代表有版本存在
            VersionStatus = u'部署版本存在，直接部署'
        else:
            # 代表没版本，需要注册版本
            VersionStatus = u'部署版本不存在，需要注册'

        PutStr("productive_list", productive_list)  # 生产环境IP列表
        PutStr("VersionStatus", VersionStatus)  # 程序包注册状态
        PutStr("PagekeVersionId", PagekeVersionId)  # 程序包版本ID
        PutStr("version", version)  # 部署版本
        PutStr("application", application)  # 应用名称
        PutStr("ftp_file_url", ftp_file_url)  # ftp下载地址
        PutStr("all_id", self.all_id)
        PutStr("one_id", self.one_id)  # ftp下载地址
        PutStr("other_id", self.other_id)  # ftp下载地址

        row = 'version={0}&application={1}&ftp_file_url={2}&VersionStatus={3}&PagekeVersionId={4}&productive_list={5}'.format(
            version,
            application,
            ftp_file_url,
            VersionStatus,
            PagekeVersionId,
            productive_list)

        PutRow('default', row)

        if productive_list:
            logging.error('发现生产环境IP，请移除生产环境IP: %s，流程将退出！' % productive_list)
            sys.exit(1)


if __name__ == '__main__':
    inspectVersion()
