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
            if result["error"] == "":
                return result["data"]
            else:
                print result
                raise Exception("response failed")
        except ValueError as e:
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

    def search_object(self, device_type, **kwargs):
        url = self.base_url + "/object/%s/instance/_search" % device_type
        return self.do_request("POST", url, json=kwargs)


####
# WARNING: codeAsile=>codeAsile (typo)
###


class IDCManager(object):

    def __init__(self, user, org, host):
        self.client = CMDBClient(user, org, host)

    def init_idc(self, name, area, building, shortname, row, column, unum, idc_args=None, idcrack_args=None):
        """
        初始化机房，以及新建一批机柜
        name: 机房名称
        area: 机房地域
        building: 机房楼层号
        shortname: 机房简称
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
            "building": building,
            "shortname": shortname
        }

        print name, area, building, shortname
        print row, column, unum
        print idc_args
        print idcrack_args

        if idc_args:
            create_idc_args.update(idc_args)

        # 创建机房
        idc = self.client.create_idc(**create_idc_args)

        idc_id = idc["instanceId"]
        rack_list = []
        rack_layout = []
        # 创建机柜
        letters = string.letters[:26].upper()
        for r in range(row):
            row_layout = []
            for c in range(1, column + 1):
                # code = '3%s-02-%02d' % (letters[r], c)  # 松山湖
                code = "%02d-%02d" % (r + 1, c)  # 寮步
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
                    "code": code,
                })

            rack_layout.append(row_layout)
        self.client.update_idc(idc_id, layout=json.dumps({
            "racks": rack_layout,
            "doors": [],
            "codeAsile": [],
        }))
        return idc_id

    def autolayout_idc(self, idc_id, row, column, isForce=False):
        """
        给指定机房自动布局机柜的信息
        idc_id: 机房ID
        row: 重排列行数
        column: 重排列列数
        isForce: 是否强制重新布局
        """
        idc = self.client.get_idc(idc_id)
        existed_layout = json.loads(idc.get("layout", "{}"))
        existed_rack_layout = existed_layout.get("racks", [])
        # 为空的时候才进行初始化
        if len(existed_rack_layout) > 0 and (not isForce):
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
                if len(idc["rack"]) >= idc_index:
                    temp_rack = idc["rack"][idc_index - 1]
                    temp_update_info = {"code": code}
                    if temp_rack.get("status", "") == "":
                        temp_update_info.update({"status": "启用"})
                    idc_update_dict.update({temp_rack["instanceId"]: temp_update_info})
                    row_layout.append({
                        "instanceId": temp_rack["instanceId"],
                        "type": "rack",
                        "code": "%s_%02d" % (letters[r], c),
                    })
                    print row_layout
                else:
                    # 这种不处理吗？
                    pass
            print row_layout
            if len(row_layout) > 0:
                layout.append(row_layout)

        print idc_update_dict
        if len(idc_update_dict) > 0:
            for idcrack_id, update_info in idc_update_dict.items():
                self.client.update_idcrack(idcrack_id, **update_info)

        return self.client.update_idc(idc_id, layout=json.dumps({
            "doors": existed_layout.get("doors", []),
            "racks": layout,
            "codeAsile": existed_layout.get("codeAsile", []),
        }))

    def check_device(self, device_type, device_id_list):
        args = {
            "query": {
                "instanceId": {"$in": device_id_list}
            },
            "fields": {
                "instanceId": 1
            }
        }
        result = self.client.search_object(device_type, **args)
        result_map = {}
        for device in result["list"]:
            result_map[device["instanceId"]] = 1
        return result_map

    def idcrack_add_device(self, idcrack_id, device_type, device_id, startU, occupiedU):
        idcrack = self.client.get_idcrack(idcrack_id)
        # 基础校验
        if not (startU > 0 and occupiedU > 0 and (startU + occupiedU) < idcrack["unum"]):
            raise Exception("起始U位和占用U位必须大于0，且不得超过可用U位")

        # 校验，1，检查机柜可用U位
        if idcrack["freeUnum"] < occupiedU:
            raise Exception("机柜U位不足")

        # 校验2，看目标U位是否被占用
        target_u_list = set(range(startU, occupiedU + startU))
        for device_layout in idcrack["layout"]:
            device_u_list = set(range(device_layout["startU"], device_layout["occupiedU"] + device_layout["startU"]))
            if len(target_u_list & device_u_list) > 0:
                raise Exception("该U位已被占用")

        if device_type != "disasble":
            check_map = self.check_device(device_type, [device_id])
            if check_map.get(device_id, 0) == 0:
                raise Exception("Object[%s] does not has Instance(%s)" % device_type, device_id)

        idcrack["layout"].append({
            "instanceId": device_id,
            "type": device_type,
            "startU": startU,
            "occupiedU": occupiedU,
        })
        self.client.update_idcrack(idcrack_id, **{
            "layout": idcrack["layout"],
            "freeUnum": idcrack["freeUnum"] - occupiedU,
        })
        return idcrack["instanceId"]

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

    def _idc_add_rack(self, idc_id, idcrack_id, code):
        return self.client.update_idcrack(idcrack_id, **{
            "_rack__IDC": [idc_id],
            "code": code,
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
        layout = json.loads(idc.get("layout", "{}"))
        racks_layout = layout.get("racks", [])
        try:
            existed_elem = racks_layout[row - 1][column - 1]
            if existed_elem["type"] == "rack":
                self._idc_remove_rack(idc, existed_elem["instanceId"])

            new_list = racks_layout[row - 1][:column - 1] + racks_layout[row - 1][column:]
            if len(new_list) > 0:
                racks_layout[row - 1] = racks_layout[row - 1][:column - 1] + racks_layout[row - 1][column:]
            else:  # 移除光了，这里将它清空掉
                racks_layout = racks_layout[:row - 1] + racks_layout[row:]

            self.client.update_idc(idc_id, layout=json.dumps({
                "racks": racks_layout,
                "doors": layout.get("doors", []),
                "codeAsile": layout.get("codeAsile", [])
            }))
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
            self._idc_add_rack(idc_id, idcrack_id, code)
            return idcrack_id

    def set_idc_element(self, idc_id, row, column, elem_type, elem_id, elem_data=None):
        """
        给机房的指定单元格设置为某元素
        存在这些case
        1. 位置不合法，并且不是边界，退出
        2. 位置不合法，是边界，且设备不是机柜，则扩展布局
        3. 位置不合法，是边界，且设备是机柜，机柜不存在(elem_id给空)，则新建机柜，扩展布局
        4. 位置不合法，是边界，且设备是机柜，机柜存在(elem_id不为空)，则直接绑定当前机房
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

        layout = json.loads(idc.get("layout", "{}"))
        racks_layout = layout.get("racks", [])
        # 添加元素应该只能在边界添加
        try:
            existed_elem = racks_layout[row - 1][column - 1]
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
            for row_index, row_layout in enumerate(racks_layout):
                valid_location.append((row_index + 1, len(row_layout) + 1))

            valid_location.append((len(racks_layout) + 1, 1))
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
            if row == len(racks_layout) + 1:
                racks_layout.append([elem])
            else:
                racks_layout[row - 1].append(elem)

        update_result = self.client.update_idc(idc_id, layout=json.dumps({
            "racks": racks_layout,
            "doors": layout.get("doors", []),
            "codeAsile": layout.get("codeAsile", [])
        }))
        return elem_id

    def _format_idcrack(self, idcrack):
        # idcrack = self.client.get_idcrack(idcrack_id)

        format_mapping = {
            "host": "HOST",
            "switch": "_SWITCH",
            "router": "_ROUTER",
            "firewall": "_FIREWALL"
        }
        layout_list = idcrack.get("layout", [])
        if len(layout_list) > 0:
            for layout in layout_list:
                layout['type'] = format_mapping.get(layout['type'], layout['type'])
            return self.client.update_idcrack(idcrack['instanceId'], layout=idcrack["layout"])
        else:
            return

    def format_idc_idcrack(self, idc_id):
        result = self.client.search_idcrack(**{
            "query": {
                "_rack__IDC": idc_id
            }
        })
        # print result
        for idcrack in result['list']:
            self._format_idcrack(idcrack)

    def format_one_idcrack(self, idcrack_id):
        idcrack = self.client.get_idcrack(idcrack_id)
        return self._format_idcrack(idcrack)

    def format_idcrack(self, query):
        result_list = self.client.search_idcrack(**query)
        for idcrack in result_list["list"]:
            return self._format_idcrack(idcrack)


# def display_idc(idc_list):
#     print "index\t实例ID\t名
#     for index, idc in enumerate(idc_list):称\t机柜数量"
#         print "%s\t%s\t%s\t%s" % (index, idc["instanceId"], idc["name"], len(idc["rack"]))


# def display_idcrack(idcrack_list):
#     for index, idcrack in enumerate(idcrack_list):
#         print index, idcrack["instanceId"], idcrack["code"], idcrack.get("unum", 0), idcrack.get("freeUnum", 0)

#         for device_layout in idcrack.get("layout", []):
#             print "\t",
#             print device_layout["startU"], device_layout["occupiedU"], device_layout["type"], device_layout["instanceId"]


if __name__ == "__main__":
    m = IDCManager("easyops", 9428447, "192.168.32.88")

    # 初始化一个机房
    # 初始化机房，以及新建一批机柜
    # name: 机房名称
    # area: 机房地域
    # building: 机房楼层号
    # shortname: 机房简称
    # row: 机房布局行数
    # column: 机房布局列数
    # unum: 机柜默认U位数
    # idc_args: 机房的其它参数，如address, memo, telphone等
    # idcrack_args: 机柜的其它参数，如type等
    idc_id = m.init_idc("智慧（寮步）数据中心", "东莞", "寮步", "LB", 6, 20, 60, {"memo": "", "address": "东莞"})

    # 加一个机柜，新建机柜
    # idcrack_id = m.set_idc_element(idc_id, 3, 1, "rack", "", {
    #     "unum": 30,
    #     "freeUnum": 30,
    # })

    # 加一个柱子
    # m.set_idc_element(idc_id, 1, 2, "column", "")

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
    # m.set_idc_element(idc_id, 2, 1, "rack", idcrack["instanceId"])

    # 将机柜重新布局为1x3的（会删除掉柱子)
    # m.autolayout_idc(idc_id, 1, 2, True)

    # 移除掉(1,2)的机柜
    # m.remove_idc_element(idc_id, 1, 2)

    # m.format_idc_idcrack("5919d6184db91")
