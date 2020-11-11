# coding=utf-8

import os
import sys
import json
import string
import requests


def get_code(row, column):
    letters = string.letters[:26].upper()
    return letters[row - 1], column


class CMDBClient(object):

    def __init__(self, user, org, host, port=80):
        self.user = user
        self.org = org
        self.host = host
        self.port = port

    def do_request(self, method, url, **kwargs):
        default_headers = {
            "org": str(self.org),
            "user": self.user,
            "host": "cmdb_resource.easyops-only.com"
        }
        headers = kwargs.get("headers", None)
        if headers:
            default_headers.update(headers)
        kwargs["headers"] = default_headers
        response = requests.request(method, url, **kwargs)
        try:
            result = response.json()
            # print result
            if result["error"] == "":
                return result["data"]
            else:
                raise Exception(result["error"])
        except ValueError as e:
            print e
            raise Exception("response is not json")

    @property
    def base_url(self):
        return "http://%s:%s" % (self.host, self.port)

    def get_idc(self, idc_id):
        url = self.base_url + "/object/_IDC/instance/%s" % idc_id
        return self.do_request("GET", url)

    def update_idc(self, idc_id, **kwargs):
        url = self.base_url + "/object/_IDC/instance/%s" % idc_id
        return self.do_request("PUT", url, json=kwargs)

    def delete_idc(self, idc_id):
        url = self.base_url + "/object/_IDC/instance/%s" % idc_id
        return self.do_request("DELETE", url)

    def search_idc(self, **kwargs):
        url = self.base_url + "/object/_IDC/instance/_search"
        return self.do_request("POST", url, json=kwargs)

    def create_idc(self, **kwargs):
        url = self.base_url + "/object/_IDC/instance"
        return self.do_request("POST", url, json=kwargs)

    def get_idcrack(self, idcrack_id):
        url = self.base_url + "/object/_IDCRACK/instance/%s" % idcrack_id
        return self.do_request("GET", url)

    def update_idcrack(self, idcrack_id, **kwargs):
        url = self.base_url + "/object/_IDCRACK/instance/%s" % idcrack_id
        return self.do_request("PUT", url, json=kwargs)

    def delete_idcrack(self, idcrack_id):
        url = self.base_url + "/object/_IDCRACK/instance/%s" % idcrack_id
        return self.do_request("DELETE", url)

    def search_idcrack(self, **kwargs):
        url = self.base_url + "/object/_IDCRACK/instance/_search"
        return self.do_request("POST", url, json=kwargs)

    def create_idcrack(self, **kwargs):
        url = self.base_url + "/object/_IDCRACK/instance"
        return self.do_request("POST", url, json=kwargs)


class IDCManager(object):

    def __init__(self, user, org, host):
        self.client = CMDBClient(user, org, host)

    def init_idc(self, name, shortname, area, row, column, unum, idc_args=None, idcrack_args=None):
        """
        初始化机房，以及新建一批机柜
        name: 机房名称
        shortname: 机房简称
        area: 机房地域
        row: 机房布局行数
        column: 机房布局列数
        unum: 机柜默认U位数
        idc_args: 机房的其它参数，如address, memo, telphone等
        idcrack_args: 机柜的其它参数，如type等
        """
        # 根据行列，批量建立机房与机柜
        create_idc_args = {
            "name": name,
            "area": area,
            "shortname": shortname
        }
        if idc_args:
            create_idc_args.update(idc_args)
        idc = self.client.create_idc(**create_idc_args)

        idc_id = idc["instanceId"]
        rack_list = []
        layout = []
        letters = string.letters[:26].upper()
        for r in range(row):
            row_layout = []
            for c in range(1, column + 1):
                code = "%s%02d" % (letters[r], c)
                create_idcrack_args = {
                    "name": "%s_%s" % (name, code),
                    "code": code,
                    "_rack__IDC": [idc_id],
                    "unum": unum,
                    "freeUnum": unum,
                    "status": "启用",
                }
                if idcrack_args:
                    create_idcrack_args.update(idcrack_args)
                rack = self.client.create_idcrack(**create_idcrack_args)
                rack_list.append(rack)
                row_layout.append({
                    "instanceId": rack["instanceId"],
                    "type": "rack",
                    "code": "%s_%02d" % (letters[r], c),
                })

            layout.append(row_layout)
        self.client.update_idc(idc_id, layout=json.dumps(layout))
        return idc_id

    # def idcrack_add_device(self, idcrack_id, device_type, device_id, startU, occupiedU):
    #     idcrack = self.client.get_idcrack(idcrack_id)
    #     # 基础校验
    #     if not (startU > 0 and occupiedU > 0 and (startU + occupiedU) < idcrack["unum"]):
    #         raise Exception("起始U位和占用U位必须大于0，且不得超过可用U位")

    #     # 校验，1，检查机柜可用U位
    #     if idcrack["freeUnum"] < occupiedU:
    #         raise Exception("机柜U位不足")

    #     # 校验2，看目标U位是否被占用
    #     target_u_list = set(range(startU, occupiedU+ startU))
    #     for device_layout in idcrack["layout"]:
    #         device_u_list = set(range(device_layout["startU"], device_layout["occupiedU"] + device_layout["startU"]))
    #         if len(target_u_list & device_u_list) > 0:
    #             raise Exception("该U位已被占用")

    #     valid_device_type = ["host", "switch", "firewall", "router", "disable"]
    #     if device_type not in valid_device_type:
    #         raise Exception("设备类型异常")

    #     idcrack["layout"].append({
    #         "instanceId": device_id,
    #         "type": device_type,
    #         "startU": startU,
    #         "occupiedU": occupiedU,
    #     })
    #     self.client.update_idcrack(idcrack_id, **{
    #         "layout": idcrack["layout"],
    #         "freeUnum": idcrack["freeUnum"] - occupiedU,
    #     })
    #     return idcrack["instanceId"]

    def sync_idcrack(self, idcrack_id):
        idcrack = self.client.get_idcrack(idcrack_id)
        update_info = self._get_idcrack_update_info(idcrack)
        print idcrack
        print idcrack["_rack__IDC"]
        # print update_info["layout"]
        # if idcrack["freeUnum"] == update_info["freeUnum"] and idcrack["layout"] == update_info["layout"]:
        #    return
        # return self.client.update_idcrack(idcrack_id, **update_info)

    def _get_idcrack_update_info(self, idcrack):
        used_unum = 0
        correct_layout = []
        # 主机
        # for host in idcrack["host"]:
        #     if not host.has_key("_occupiedU") and not host.has_key("_startU"): continue
        #     used_unum += host["_occupiedU"]
        #     correct_layout.append({
        #         "instanceId": host["instanceId"],
        #         "type": "HOST",
        #         "startU": host["_startU"],
        #         "occupiedU": host["_occupiedU"],
        #     })

        for switch in idcrack["switch"]:
            if not switch.has_key("_occupiedU") and not switch.has_key("_startU"): continue
            used_unum += switch["_occupiedU"]
            correct_layout.append({
                "instanceId": switch["instanceId"],
                "type": "_SWITCH",
                "startU": switch["_startU"],
                "occupiedU": switch["_occupiedU"],
            })

        for router in idcrack["router"]:
            if not router.has_key("_occupiedU") and not router.has_key("_startU"): continue
            used_unum += router["_occupiedU"]
            correct_layout.append({
                "instanceId": router["instanceId"],
                "type": "_ROUTER",
                "startU": router["_startU"],
                "occupiedU": router["_occupiedU"],
            })

        for firewall in idcrack["_firewall"]:
            if not firewall.has_key("_occupiedU") and not firewall.has_key("_startU"): continue
            used_unum += firewall["_occupiedU"]
            correct_layout.append({
                "instanceId": firewall["instanceId"],
                "type": "_FIREWALL",
                "startU": firewall["_startU"],
                "occupiedU": firewall["_occupiedU"],
            })

        # 宿主机
        # for vhc in idcrack["VMWARE_HOST"]:
        #     if not vhc.has_key("_occupiedU") and not vhc.has_key("_startU"): continue
        #     used_unum += vhc["_occupiedU"]
        #     correct_layout.append({
        #         "instanceId": vhc["instanceId"],
        #         "type": "VMWARE_HOST_COMPUTER",
        #         "startU": vhc["_startU"],
        #         "occupiedU": vhc["_occupiedU"],
        #     })

        # 带外
        for vhc in idcrack["OUT_OF_BAND_MANAGEMENT"]:
            if not vhc.has_key("_occupiedU") and not vhc.has_key("_startU"): continue
            used_unum += vhc["_occupiedU"]
            correct_layout.append({
                "instanceId": vhc["instanceId"],
                "type": "OUT_OF_BAND_MANAGEMENT",
                "startU": vhc["_startU"],
                "occupiedU": vhc["_occupiedU"],
            })

        for securtity in idcrack["SECURITY_SYSTEM"]:
            if not securtity.has_key("_occupiedU") and not securtity.has_key("_startU"): continue
            used_unum += securtity["_occupiedU"]
            correct_layout.append({
                "instanceId": securtity["instanceId"],
                "type": "SECURITY_SYSTEM",
                "startU": securtity["_startU"],
                "occupiedU": securtity["_occupiedU"],
            })

        for securtity in idcrack["STORAGE_DEVICE"]:
            if not securtity.has_key("_occupiedU") and not securtity.has_key("_startU"): continue
            used_unum += securtity["_occupiedU"]
            correct_layout.append({
                "instanceId": securtity["instanceId"],
                "type": "STORAGE_DEVICE",
                "startU": securtity["_startU"],
                "occupiedU": securtity["_occupiedU"],
            })

        free_unum = idcrack["unum"] - used_unum
        return {
            "freeUnum": free_unum,
            "layout": correct_layout,
        }

    def sync_all_idcrack(self):
        """
        同步机柜上的设备的占用U位的信息
        """
        result = self.client.search_idcrack(**{
            "page": 1,
            "page_size": 3000,
            "query": {},
            "fields": {
                "instanceId": 1,
                "unum": 1,
                "freeUnum": 1,
                "layout": 1,
                # 主机
                # "host._startU": 1,
                # "host._occupiedU": 1,
                # 网络设备
                "_firewall._startU": 1,
                "_firewall._occupiedU": 1,
                "switch._startU": 1,
                "switch._occupiedU": 1,
                "router._startU": 1,
                "router._occupiedU": 1,
                # 宿主机
                # "VMWARE_HOST._startU": 1,
                # "VMWARE_HOST._occupiedU": 1,
                # 带外
                "OUT_OF_BAND_MANAGEMENT._startU": 1,
                "OUT_OF_BAND_MANAGEMENT._occupiedU": 1,
                "SECURITY_SYSTEM._startU": 1,
                "SECURITY_SYSTEM._occupiedU": 1,
                "STORAGE_DEVICE._startU": 1,
                "STORAGE_DEVICE._occupiedU": 1
            }
        })

        idcrack_list = result['list']
        update_result = []
        for idcrack in idcrack_list:
            try:
                update_info = self._get_idcrack_update_info(idcrack)
            except Exception as e:
                print e
                continue

            print "checking update idcrack for %s" % idcrack["instanceId"]
            if idcrack.get("freeUnum", 0) != update_info["freeUnum"] or idcrack.get("layout", []) != update_info[
                "layout"]:
                temp_result = self.client.update_idcrack(idcrack["instanceId"], **update_info)
                update_result.append(temp_result)
        return update_result

    def autolayout_idc(self, idc_id, row, column, isForce=False):
        """
        给指定机房自动布局机柜的信息
        idc_id: 机房ID
        row: 重排列行数
        column: 重排列列数
        isForce: 是否强制重新布局
        """
        idc = self.client.get_idc(idc_id)
        existed_layout = json.loads(idc.get("layout", "[]"))
        # 为空的时候才进行初始化
        if len(existed_layout) > 0 and (not isForce):
            raise Exception("机房已有布局")

        if len(idc["rack"]) == 0:
            raise Exception("机房尚无机柜，不需要布局")

        if len(idc["rack"]) > row * column:
            raise Exception("机柜数量%d大于(%dx%d)，请重新输入row与column" % (len(idc["rack"]), row, column))

        idc_update_dict = {}
        layout = []
        letters = string.letters[:26].upper()
        for r in range(row):
            row_layout = []
            for c in range(1, column + 1):
                code = "%s%02d" % (letters[r], c)
                idc_index = (r * column) + c
                if len(idc["rack"]) > idc_index:
                    temp_rack = idc["rack"][idc_index]
                    temp_update_info = {"code": code}
                    if temp_rack.get("status", "") != "":
                        temp_update_info.update({"status": "启用"})
                    idc_update_dict.update({temp_rack["instanceId"]: temp_update_info})
                    row_layout.append({
                        "instanceId": temp_rack["instanceId"],
                        "type": "rack",
                        "code": "%s_%02d" % (letters[r], c),
                    })
                else:
                    # 这种不处理吗？
                    pass
            if len(row_layout) > 0:
                layout.append(row_layout)

        if len(idc_update_dict) > 0:
            for idcrack_id, update_info in idc_update_dict.items():
                self.client.update_idcrack(idcrack_id, **update_info)

        return self.client.update_idc(idc_id, layout=json.dumps(layout))

    def _idc_remove_rack(self, idc, idcrack_id):
        """
        移除机房和机柜的关系
        """

        for rack in idc["rack"]:
            if rack["instanceId"] != idcrack_id:
                continue
            return self.client.update_idcrack(idcrack_id, **{
                "_rack__IDC": [],
            })

    def _idc_add_rack(self, idc_id, idcrack_id):
        return self.client.update_idcrack(idcrack_id, **{
            "_rack__IDC": [idc_id]
        })

    def remove_idc_element(self, idc_id, row, column):
        """
        给机房指定位置移除元素
        idc_id: 机房ID
        row: 行
        column: 列

        如以下例子：
        A B C
        D E F
        G

        移除(3,1)，之后布局会变成
        A B C
        D E F
        """
        idc = self.client.get_idc(idc_id)
        layout = json.loads(idc.get("layout", "[]"))
        try:
            existed_elem = layout[row - 1][column - 1]
            if existed_elem["type"] == "rack":
                self._idc_remove_rack(idc, existed_elem["instanceId"])

            new_list = layout[row - 1][:column - 1] + layout[row - 1][column:]
            if len(new_list) > 0:
                layout[row - 1] = layout[row - 1][:column - 1] + layout[row - 1][column:]
            else:  # 移除光了，这里将它清空掉
                layout = layout[:row - 1] + layout[row:]

            self.client.update_idc(idc_id, layout=json.dumps(layout))
        except IndexError as e:
            print "坐标不在范围内，忽略"

    # def _idc_can_set_idcrack(self, idc_id, idcrack_id):
    #     idcrack = self.client.get_idcrack(idcrack_id)

    def _create_or_set_idcrack(self, idc_id, idc_name, idcrack_id, code, idcrack_data=None):
        if not idcrack_id:
            default_create_info = {
                "name": "%s_%s" % (idc_name, code),
                "code": code,
                "status": "启用",
                "_rack__IDC": [idc_id],
            }
            if idcrack_data:
                default_create_info.update(idcrack_data)
            created_idcrack = self.client.create_idcrack(**default_create_info)
            return created_idcrack["instanceId"]
        else:
            # 这里强行添加，如果不存在，就给失败了？
            self._idc_add_rack(idc_id, idcrack_id)
            return idcrack_id

    def set_idc_element(self, idc_id, row, column, elem_type, elem_id, elem_data=None):
        """
        给机房的指定单元格设置为某元素
        存在这些case
        1. 位置不合法，并且不是边界，退出
        2. 位置不合法，是边界，且设备不是机柜，则扩展布局
        3. 位置不合法，是边界，且设备是机柜，机柜不存在(elem_id给空)，则新建机柜，扩展布局
        4. 位置不合法，是边界，且设备是机柜，机柜存在(elem_id给空)，但直接绑定当前机房
        5. 位置合法，且该位置不是是机柜，则直接替换
        6. 位置合法，且该位置是机柜，则解除旧的机柜关系，新建设备与否与上面相同

        idc_id: 机房ID
        row: 行数
        column: 列数
        elem_type: 类型，只能在["rack", "aisle", "column", "distributor"]之中选
        elem_id: ID，如果是aisle, column, distributor，可不填。如果是机柜，如果是已有机柜则填该机柜id，否则不填按新建处理
        elem_data: 新建机柜的信息
        """

        ALL_TYPE = ["rack", "aisle", "column", "distributor"]
        if elem_type not in ALL_TYPE:
            raise Exception("elem_type should in [rack, aisle, column, distributor]")
        idc = self.client.get_idc(idc_id)
        layout = json.loads(idc.get("layout", "[]"))
        # 添加元素应该只能在边界添加

        try:
            existed_elem = layout[row - 1][column - 1]
            if existed_elem["type"] == "rack":
                print u"机柜替换掉，只移除关系, %s" % existed_elem
                self._idc_remove_rack(idc, existed_elem["instanceId"])
            else:  # 如果是这种不是机柜，就可以直接取而代之
                print u"原来是配电柜过道等，直接替换"

            if elem_type == "rack":
                elem_id = self._create_or_set_idcrack(idc_id, idc["name"], elem_id, existed_elem["code"], elem_data)

            existed_elem["type"] = elem_type
            existed_elem["instanceId"] = elem_id

        except IndexError as e:
            valid_location = []
            for row_index, row_layout in enumerate(layout):
                valid_location.append((row_index + 1, len(row_layout) + 1))

            valid_location.append((len(layout) + 1, 1))
            # 追加元素
            if (row, column) not in valid_location:
                message = """只能在机柜的边界添加元素:
以一个布局为例，左上角为(1,1)，下面只能在(1, 4), (2,2), (3, 2), (4,1) 增加元素
A B C +
D + 
F +
+
当前机房的可用位置如下：%s
                """ % valid_location
                raise Exception(message)

            code = "%s%02d" % get_code(row, column)
            if elem_type == "rack":
                elem_id = self._create_or_set_idcrack(idc_id, idc["name"], elem_id, code, elem_data)

            elem = {
                "instanceId": elem_id,
                "type": elem_type,
                "code": "%s_%02d" % get_code(row, column)
            }
            if row == len(layout) + 1:
                layout.append([elem])
            else:
                layout[row - 1].append(elem)

        update_result = self.client.update_idc(idc_id, layout=json.dumps(layout))
        return elem_id


# def display_idc(idc_list):
#     print "index\t实例ID\t名称\t机柜数量"
#     for index, idc in enumerate(idc_list):
#         print "%s\t%s\t%s\t%s" % (index, idc["instanceId"], idc["name"], len(idc["rack"]))


# def display_idcrack(idcrack_list):
#     for index, idcrack in enumerate(idcrack_list):
#         print index, idcrack["instanceId"], idcrack["code"], idcrack.get("unum", 0), idcrack.get("freeUnum", 0)

#         for device_layout in idcrack.get("layout", []):
#             print "\t",
#             print device_layout["startU"], device_layout["occupiedU"], device_layout["type"], device_layout["instanceId"]


if __name__ == "__main__":
    m = IDCManager("defaultUser", EASYOPS_ORG, EASYOPS_LOCAL_IP)

    ### 1
    # 初始化一个机房（名称：凤岗1F01，简称：FG01，地域：凤岗，行数：10，列数：10，机柜的总U位数：48，机柜其他属性信息：{"memo": "凤岗云测试机房", "address":"凤岗李坑路1号"}）
    # idc_id = m.init_idc("凤岗1F01", "FG01", "凤岗", 10, 10, 48, {"memo": "凤岗云测试机房", "address":"凤岗李坑路1号"})

    ### 2
    # "rack": 机柜, "aisle"：过道, "column"：柱子, "distributor"：配电柜

    # 将某个机柜变为柱子：（机房的instanceId, 哪行，哪列，"column"，""）
    # m.set_idc_element('5947418c9262d', 8, 9, "column", "")
    # 将某个机柜变为配电柜：（机房的instanceId, 哪行，哪列，"column"，""）
    # m.set_idc_element('5947418c9262d', 3, 4, "distributor", "")

    ### 3
    # 将某一列变为过道
    # for i in range(1, 11):
    #    m.set_idc_element('5947418c9262d', i, 6, "aisle", "")

    ### 4
    # 移除某个机柜：（机房instanceId，哪行，哪列）
    # m.remove_idc_element('5947418c9262d', 10, 9)

    ### 5
    # 设备跟机柜添加关联关系后，需要同步生成机柜的布局信息，参数：机柜实例instanceId
    # m.sync_idcrack('5a465a068f296')
    m.sync_all_idcrack()

    ######################################

    # m.set_idc_element('5945d3f78e913', 1, 6, "rack", '5945d3f85df4b')

    # m.autolayout_idc('5945c0a1f0e7b', 10, 10, True)

    # m.set_idc_element('593560830b82c', 1, 2, "rack", "593562f22604d")

    '''
    idcrack = m.client.create_idcrack(**{
         "name": "凤岗A03",
         "code": "A03",
         "unum": 48,
         "freeUnum": 48,
         "status": "启用",
         "memo": "",
         "type": "普通柜",
    })

    # 下一行加一个已存在的机柜
    #m.set_idc_element('5945c0a1f0e7b', 1, 3, "rack", idcrack)
    '''

    # 加一个机柜，新建机柜
    # idcrack_id = m.set_idc_element(idc_id, 1, 2, "rack", "", {
    #     "unum": 30,
    #     "freeUnum": 30,
    # })

    # idcrack = m.client.create_idcrack(**{
    #     "name": "new_created",
    #     "code": "B01",
    #     "unum": 24,
    #     "freeUnum": 24,
    #     "status": "启用",
    #     "memo": "测试机柜",
    #     "type": "普通柜",
    # })
    # 下一行加一个已存在的机柜
    # m.set_idc_element('593560830b82c', 1, 11, "rack", '593561db421c4')

    # 将机柜重新布局为1x3的（会删除掉柱子)
    # m.autolayout_idc('593560830b82c', 15, 15, True)