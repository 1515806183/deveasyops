# encoding: utf-8
import requests, json, logging, sys

easyops_org = "3087"
cmdb_host = "10.163.128.232"
cmdb_headers = {'host': 'cmdb_resource.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                'content-Type': 'application/json'}

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S')

# easyops_org = "3087"
# cmdb_host = "10.163.128.232"
# APP_NAME = 'fcodeTest20201230'
# clusterType = "生产"


# DEPLOY_SUMMARY = json.dumps({"failed": 2, "deploy_detail": [
#     {"status": "failed", "package_name": "fcodeTest20201230", "pre_version_name": "4..01", "ip": "100.116.1.132",
#      "package_type": "\u7a0b\u5e8f\u5305", "version_name": "4..01"},
#     {"status": "failed", "package_name": "fcodeTest20201230", "pre_version_name": "4..01", "ip": "100.116.2.192",
#      "package_type": "\u7a0b\u5e8f\u5305", "version_name": "4..01"}], "total": 2, "success": 0})

# pageke_env_type = '15'  # 1为开发，3为测试，15为生产，程序包版本
# 0开发， 1 测试， 2生产
pageke_env_type = ''
if clusterType == '开发':
    clusterType = '0'
    pageke_env_type = '1'
elif clusterType == '测试':
    clusterType = '1'
    pageke_env_type = '3'
elif clusterType == '生产':
    clusterType = '2'
    pageke_env_type = '15'


def run():
    # 获取部署结果-里面的包的前一个版本
    try:
        deploy_detail = json.loads(DEPLOY_SUMMARY).get('deploy_detail')
        logging.info(u'部署结果信息:%s' % deploy_detail)

        if len(deploy_detail) > 0:
            pre_version_name = deploy_detail[0].get('pre_version_name')
            logging.info(u'要回滚的程序包版本:%s' % pre_version_name)
            if not pre_version_name:
                logging.error(u'应用属于第一次部署，没有前一个版本信息，回滚部署将退出')
                sys.exit(1)

            GetVersionInfo().CheckVersion(pre_version_name)  # 检查包是否存在
        else:
            logging.error(u'应用属于第一次部署，没有前一个版本信息，回滚部署将退出')
            sys.exit(1)
    except Exception as e:
        logging.error(u'应用属于第一次部署，没有前一个版本信息，回滚部署将退出')
        sys.exit(1)


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


class GetVersionInfo():
    """
    获取部署策略ID
    """

    def DeployInfo(self, pre_version_name):
        params = {
            "query": {
                "name": {"$eq": APP_NAME},

            },
            "fields": {
                "instanceId": True,
                "_packageList": True
            },
            "only_relation_view": True,
            "only_my_instance": False,
            "page_size": 1
        }

        logging.info('%s' % params)
        try:
            url = "http://{HOST}/object/APP/instance/_search".format(HOST=cmdb_host)
            data = http_post('POST', url, params=params)
            if not data:
                logging.error('查询不到应用:%s,将退出部署' % APP_NAME)
                sys.exit(1)

            packageList = data[0].get('_packageList', [])

            if len(packageList) == 0:
                raise Exception('该应用没有程序包')
            packageId = packageList[0]['packageId']
            # logging.info('查询应用的程序包的ID为：%s' % str(packageId))

            # 根据packageId 获取所有的程序包
            packageId_headers = {'host': 'deploy.easyops-only.com', 'org': easyops_org, 'user': "defaultUser",
                                 'content-Type': 'application/json'}
            payload = {}
            version_result = []
            version_page = 1
            while True:
                url = "http://{host}/version/list?packageId={packageId}&page={page}&pageSize=300".format(
                    packageId=packageId, page=version_page, host=cmdb_host)
                response = requests.request("GET", url, headers=packageId_headers, data=payload)
                result = response.json()
                if result['data']['list'] and len(result['data']['list']) > 0:
                    data_list = result['data']['list']
                    version_result = version_result + data_list
                    version_page += 1
                else:
                    break

            for data in version_result:
                name = str(data.get('name'))  # 程序包名称
                env_type = str(data.get('env_type'))  # 运行环境。3 测试
                if (name == str(pre_version_name)) and (env_type == pageke_env_type):
                    versionId = str(data.get('versionId'))  # 程序包版本
                    logging.info('查询到程序包的名称:%s' % name)
                    logging.info('查询到程序包的版本:%s' % str(versionId))
                    logging.info('查询到程序包的类型:%s' % env_type)
                    return versionId

        except Exception as e:
            raise Exception('应用没有关联程序包')

    def CheckVersion(self, pre_version_name):
        """
        根据输入的版本，校验版本是否正确
        :return:
        """
        # 获取部署策略ID
        versionId = self.DeployInfo(pre_version_name)

        if not versionId:
            logging.info('%s is not version %s' % (APP_NAME, pre_version_name))
            sys.exit(1)

        PutStr("RollbackversionId", versionId)  # 回滚版本ID
        PutStr("RollbackversionName", pre_version_name)  # 回滚版本号
        row = 'RollbackversionName={0}&RollbackversionId={1}&APP_NAME={2}'.format(pre_version_name, versionId, APP_NAME)
        PutRow('default', row)


if __name__ == '__main__':
    run()
