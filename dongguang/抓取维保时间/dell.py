# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import sys
reload(sys)
sys.setdefaultencoding('utf8')

chrome_opt = Options()  # 创建参数设置对象.
# chrome_opt.add_argument('--headless')  # 无界面化.
# chrome_opt.add_argument('--disable-gpu')  # 配合上面的无界面化.
# chrome_opt.add_argument('--window-size=1366,768')  # 设置窗口大小, 窗口大小会有影响.
# 静止加载图片
prefs = {
    'profile.default_content_setting_values': {
        'images': 2
    }
}
chrome_opt.add_experimental_option('prefs', prefs)

# 创建Chrome对象并传入设置信息.
driver = webdriver.Chrome(chrome_options=chrome_opt)


def getDellSn(sn):
    # 操作这个对象.
    driver.get('https://www.dell.com/support/home/zh-cn?app=products&~ck=mn')  # get方式访问百度.
    time.sleep(2)
    input_str = driver.find_element_by_id('inpEntrySelection')
    input_str.send_keys(sn)
    button = driver.find_element_by_id('txtSearchEs')
    button.click()
    time.sleep(7)

    # print(driver.page_source)       # 打印加载的page code, 证明(prove) program is right.
    data = driver.find_element_by_id('warrantyExpiringLabel')
    return data.text


with open('./sn.txt', 'r') as f:
    data_list = f.readlines()

for sn in data_list:
    try:
        data = getDellSn(sn.split('\n'[0]))
    except Exception as e:
        data = 'None'

    res = str(sn.split('\n')[0]) + '----' + ''.join(data) + '\n'
    print res
    with open('./sn_data.txt', 'a+') as f:
        f.write(res)

    time.sleep(2)


driver.quit()  # 使用完, 记得关闭浏览器, 不然chromedriver.exe进程为一直在内存中

