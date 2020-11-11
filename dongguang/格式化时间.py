# -*- coding:utf-8 -*-
import time, requests, json, subprocess, re
import threading
from Queue import Queue
from gevent import monkey
import gevent
from gevent.pool import Pool

monkey.patch_all()

with open('./sn.txt') as f:
    data_list = f.readlines()


class ThreadInsert(object):
    def __init__(self):
        self.pool = Pool(20)
        start_time = time.time()
        self.data = self.getData()
        self.task()
        # self.mysql_delete()
        print("========= 数据更新完成,共耗时:{}'s =========".format(round(time.time() - start_time, 3)))

        # 从本地的文件中读取数据

    def getData(self):
        st = time.time()

        with open('./sn.txt') as f:
            data_list = f.readlines()

        n = 10  # 按每1000行数据为最小单位拆分成嵌套列表，可以根据实际情况拆分
        result = [data_list[i:i + n] for i in range(0, len(data_list), n)]
        print("共获取{}组数据,每组{}个元素.==>> 耗时:{}'s".format(len(result), n, round(time.time() - st, 3)))
        return result

    def dealdata(self, content):
        res = []
        for i in content:
            res.append(self.pool.spawn(self.gevent_data, i))
        gevent.joinall(res)

    def gevent_data(self, i):
        data = str(i).split('----')
        sn = data[0]

        data_list = data[1].split(' ')
        ri = data_list[1]
        yue = re.search(r'\d+', data_list[2]).group()
        if len(yue)== 1:
            yue = str(0) + str(yue)
        nian = re.search(r'\d+', data_list[-1]).group()
        datedata = str(nian) + '-' + str(yue) + '-' + str(ri)
        print sn + '----' + datedata

        # sn = data[0].split('\t')[0].strip(' ')
        # outtime = data[1].strip(' ')
        # # print sn.split('\t')[0].strip(' ') + '----' + outtime
        # outtime_list = outtime.split(' ')
        # year = outtime_list[-1].split('\n')[0]
        # day = outtime_list[1]
        # mon = outtime_list[1]
        # day = re.search(r'\d+', day).group()
        # mon = re.search(r'\d+', mon).group()
        # dataouttime = year + '-' + str(mon) + '-' + str(day)
        # res = sn + '         ----------------    ' + dataouttime
        # print res

    # 开启多线程任务
    def task(self):
        # 设定最大队列数和线程数
        q = Queue(maxsize=10)
        st = time.time()
        while self.data:
            content = self.data.pop()
            t = threading.Thread(target=self.dealdata, args=(content,))
            q.put(t)
            if (q.full() == True) or (len(self.data)) == 0:
                thread_list = []
                while q.empty() == False:
                    t = q.get()
                    thread_list.append(t)
                    t.start()
                for t in thread_list:
                    t.join()
        # print("数据插入完成.==>> 耗时:{}'s".format(round(time.time() - st, 3)))


if __name__ == '__main__':
    ThreadInsert()
