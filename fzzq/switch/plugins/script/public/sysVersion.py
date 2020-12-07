# encoding: utf-8
import re

'''
@author: Peach
@license: (C) Copyright 2016-2020, Personal exclusive right.
@contact: peachtao@easyops.cn
@software: tool
@application:
@file: sysVersion.py
@time: 2020/12/2 11:56
@desc:
'''

def get_sysVersion(data):
    data = data.strip('\n')
    print data
    try:
        version = re.search(r'SNMPv2-SMI::enterprises.35047.2.1.1.7.0 = STRING: (.*)', data)
        print version
    except Exception as e:
        print e
    return
