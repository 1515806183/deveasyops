# -*- coding: utf-8 -*-
import requests
import time, json

t = time.time()
times = str(int(round(t * 1000)))
save_f = open('./sn_data.txt', 'w+')


def get_sn(sn_code):
    url = 'http://es.h3c.com/entitlement/query'
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    data = "serialNumber=%s&language=CN&_d=%s&mvs=N" % (sn_code, times)
    try:
        r = requests.post(url, data=data, headers=headers)
        result = json.loads(r.content)
        if result['code'] == 200:
            res = result['data']['es'][0].get('combinedUnitEntitlement')
            # 合同开始时间
            overallContractStartDate = res.get('overallContractStartDate')
            # 合同结束时间
            overallContractEndDate = res.get('overallContractEndDate')
            data = sn_code + '----' + overallContractStartDate + '----' + overallContractEndDate + '\n'
        else:
            data = sn_code + '----' + 'None' + '----' + 'None' + '\n'
        print data
        save_f.write(data)
    except Exception as e:
        data = sn_code + '----' + 'None' + '----' + 'None' + '\n'
        save_f.write(data)


with open('./sn.txt', 'r') as f:
    data_list = f.readlines()

for sn_code in data_list:
    get_sn(sn_code.split('\n')[0])

save_f.close()
