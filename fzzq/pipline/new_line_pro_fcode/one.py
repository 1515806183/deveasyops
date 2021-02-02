# coding:utf-8
import requests, json, time, logging, sys

reload(sys)
sys.setdefaultencoding('utf8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# application = "fcodeTest20201230"
# clusterType = "生产"
# pageke_env_type = "生产"

logging.info('部署的应用名称: %s' % application)
logging.info('部署应用的集群类型: %s' % clusterType)
logging.info('部署应用程序包类型: %s' % pageke_env_type)

# 集群类型 0开发， 1 测试 2 生产
if clusterType == "开发":
    clusterType = '0'
elif clusterType == "测试":
    clusterType = '1'
elif clusterType == "生产":
    clusterType = '2'

# 包类型
if pageke_env_type == '开发':
    pageke_env_type = '1'
elif pageke_env_type == '测试':
    pageke_env_type = '3'
elif pageke_env_type == '生产':
    pageke_env_type = '15'

# cmdb_host = str(EASYOPS_CMDB_HOST).split(':')[0]
# easyops_org = str(EASYOPS_ORG)
cmdb_host = "10.163.128.232"
easyops_org = "3087"
# header配置
cmdb_headers = {
    'host': "cmdb_resource.easyops-only.com",
    'org': easyops_org,
    'user': "defaultUser",
    'content-Type': 'application/json'
}

deploy_headers = {
    'host': 'deploy.easyops-only.com',
    'org': easyops_org,
    'user': 'defaultUser',
    'content-Type': 'application/json',
}


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


class FrontWork():
    def __init__(self):
        pass

    # 获取fcode参数
    def get_fcode_params(self):
        logging.info('开始收集fcode参数')
        params = {
            "query": {
                "APP.name": {
                    "$eq": application
                }

            },
            "fields": {
                "business": True,
                "ftp_url": True,
                "operator": True,
                "version": True,
                "online_date": True,
                "name": True,
                "commitId": True,
                "APP.instanceId": True

            }
        }

        url = "http://{HOST}/object/FCODE_FLOW/instance/_search".format(HOST=cmdb_host)
        focde_data = http_post('POST', url, params=params)  # list
        if not focde_data:
            logging.error('无法获取fcode流水号信息')
            exit(1)

        focde_data = focde_data[0]
        version = str(focde_data.get('version'))  # 部署版本

        # 0开发， 1 测试 2 生产
        if clusterType == '0':
            version += '-DEV'
        elif clusterType == '1':
            version += '-UAT'
        # elif clusterType == "2":
        #    version += '-PRO'
        self.version = version
        focde_data['version'] = self.version  # 区分版本-加后缀

        self.FullID = ''
        self.OneID = ''
        self.OtherID = ''
        try:
            app_info = focde_data.get('APP')
            if not app_info:
                logging.error('检查后台fcode脚本，Fcode流水号与应用关联错误')
                exit(1)

            app_id = app_info[0].get('instanceId')  # 应用ID

            url = "http://{HOST}:8061/deployStrategy?appId={ID}".format(HOST=cmdb_host,
                                                                        ID=app_id)
            data_list = http_post('GET', url, headers=deploy_headers)
            if not data_list:
                logging.error('无法获取应用程序部署策略，策略为空')
                exit(1)

            for app_info_data in data_list:
                cluster_type = str(app_info_data.get('clusterType'))
                if cluster_type == clusterType:
                    name = app_info_data.get('name')
                    id = app_info_data.get('id')
                    if u'全量部署' == name:
                        self.FullID = id
                    elif u'灰度1台机器部署' == name:
                        # PutStr("one_id", id)
                        self.OneID = id
                    elif u'灰度其他机器部署' == name:
                        # PutStr("other_id", id)
                        self.OtherID = id

            if self.FullID == '' and self.OneID == '' and self.OtherID == '':
                logging.error('未设置部署策略, 请创建部署策略')
                exit(1)

        except Exception as e:
            raise Exception('先创建部署策略')

        self.online_id = focde_data.get('name')  # 流水号
        self.version = focde_data.get('version')  # 部署版本名称
        self.operator = focde_data.get('operator', "easyops")  # 上线角色
        self.online_date = focde_data.get('online_date')  # 上线时间
        self.business = focde_data.get('business')  # 业务系统
        self.ftp_url = focde_data.get('ftp_url')  # ftp下载地址
        self.commitId = focde_data.get('commitId')  # git提交ID
        code, PagekeVersionId = self.inspect_version()
        return code, PagekeVersionId

    # 检查版本， 如果存在，返回True, 程序包版本ID
    def inspect_version(self):

        """
        :param version: 程序包版本，又是程序包名称
        :param commitId: git ID
        :return:
        """

        logging.info('检查包的版本号：%s，commitId:%s' % (self.version, self.commitId))

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
                    '应用程序没有包。请先创建一个包。包名称与应用程序名称相同')
                exit(1)

            versionId = ''
            for package in packageList:
                packageId = package.get('packageId')  # 程序包ID
                logging.info('要开始查找的包ID:%s' % packageId)

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
                    if (name == self.version) and (env_type == pageke_env_type) and (
                            commit_id == self.commitId):  # 如果版本相同，commitid相同 环境相同则有这个包
                        versionId = data.get('versionId')  # 程序包版本
                        falg = True
                        return True, versionId
                if falg:
                    logging.warning("找到包，包的版本ID:%s" % versionId)
                    return True, versionId
            else:
                logging.warning('没有找到部署的程序包版本，需要注册版本')
                return False, False

        except Exception as e:
            print e
            raise Exception('获取应用没有程序包出错')

    def run(self):
        code, PagekeVersionId = self.get_fcode_params()

        if not PagekeVersionId:
            PagekeVersionId = u'无'

        if code:
            # 代表有版本存在
            VersionStatus = u'部署版本存在，直接部署'
            PutStr("VersionStatus", VersionStatus)
        else:
            # 代表没版本，需要注册版本
            VersionStatus = u'部署版本不存在，需要注册'
            PutStr("VersionStatus", VersionStatus)

        PutStr("online_id", self.online_id)
        PutStr("version", self.version)
        PutStr("operator", self.operator)
        PutStr("online_date", self.online_date)
        PutStr("business", self.business)
        PutStr("ftp_url", self.ftp_url)
        PutStr("commitId", self.commitId)
        PutStr("PagekeVersionId", PagekeVersionId)  # 程序包版本ID
        PutStr("VersionStatus", VersionStatus)
        PutStr("application", application)
        PutStr("FullID", self.FullID)
        PutStr("OneID", self.OneID)
        PutStr("OtherID", self.OtherID)

        row = u'online_id={0}&version={1}&operator={2}&online_date={3}&application={4}&business={5}&ftp_url={6}&commitId={7}&PagekeVersionId={8}&VersionStatus={9}'.format(
            self.online_id,
            self.version, self.operator, self.online_date, application, self.business, self.ftp_url, self.commitId,
            PagekeVersionId, VersionStatus

        )
        PutRow('default', row)


if __name__ == '__main__':
    FrontWork().run()
