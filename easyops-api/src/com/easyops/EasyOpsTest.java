package com.easyops;


import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import net.sf.json.JSONArray;

import java.util.HashMap;
import java.util.Map;

public class EasyOpsTest {
    public static void main(String[] args) {

        EasyOps easyops = new EasyOps("192.168.10.144", "bbf2c57378fd37c2623372ea",
                "6f7a776c4c5943715742476c7475556b56464f4f6a5973526a53484549664468");




//        System.out.println("******************GET-查询所有资源模型******************");
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        get_params.put("page_size", "1");
//        get_params.put("page", "1");
//        String ret = easyops.sendRequest("/cmdb_resource/object", get_params, "GET");
//        System.out.println(ret);


        System.out.println("******************POST-根据IP查询主机实例******************");
        Map<String, Object> get_params = new HashMap<String, Object>();
        get_params.put("page_size", "10");
        get_params.put("page", "1");
//        Map<String,Object> query_map = new HashMap<>();
//        query_map.put("ip","192.168.10.144")
//        get_params.put("query",query_map);
        Map<String,Object> fields_map = new HashMap<>();
        fields_map.put("ip",true);
        fields_map.put("instanceId",true);

        get_params.put("fields",fields_map);
        String ret = easyops.sendRequest("/cmdb_resource/object/HOST/instance/_search", get_params, "POST");
        System.out.println(ret);

//        net.sf.json.JSONObject jsonObject = net.sf.json.JSONObject.fromObject(ret);
//        JSONArray array = JSONArray.fromObject(jsonObject.get("data"));
//        System.out.println(array);
//        net.sf.json.JSONObject  object = net.sf.json.JSONObject.fromObject(jsonObject.get("data"));
//        System.out.println("object:"+object);







//
//
//        System.out.println("******************PUT-修改实例关系metadata\n******************");
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        get_params.put("page_size", "10");
//        get_params.put("page", "1");
//        String ret = easyops.sendRequest("/cmdb_resource/v2/object/HOST/instance/@instance_id", get_params, "PUT");
//        System.out.println(ret);
//
//
//
//        System.out.println("******************get-获取拓扑规则\n*******返回规则object，解析规则id拼装拓扑地址 ***********");
////        eg：http://42.159.91.26/brick/HOST/instance/5b163707ca688/topology/d527db788f82afc63f81b40c5d63fe5965ac7c44
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        get_params.put("objectId", "HOST");
//        get_params.put("instanceId", "5b163707ca688");
//        String ret = easyops.sendRequest("/graph/topology/rule", get_params, "GET");
//        System.out.println(ret);
//        net.sf.json.JSONObject jsonObject = net.sf.json.JSONObject.fromObject(ret);
//        JSONArray array = JSONArray.fromObject(jsonObject.get("data"));
////        net.sf.json.JSONObject  object = net.sf.json.JSONObject.fromObject(jsonObject.get("data"));
//        System.out.println(array);
//        net.sf.json.JSONObject obj = (net.sf.json.JSONObject) array.get(0);
//        System.out.println("===:" + obj.get("rule_id"));
//        System.out.println("拓扑url:http://42.159.91.26/brick/HOST/instance/5b163707ca688/topology/" + obj.get("rule_id"));


//        System.out.println("******************post-设置关系:如果关系存在就会删除\n******************");
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        //数据转为map
//        JSONArray array = new JSONArray();
//        array.add("5b163707ca688");
//        JSONArray array2 = new JSONArray();
//        array2.add("5b4dfb24cf28b");
//        get_params.put("instance_ids", array);
//        get_params.put("related_instance_ids", array2);
//
//        String ret = easyops.sendRequest("/cmdb_resource/object/HOST/relation/owner/set", get_params, "POST");
//        System.out.println(ret);




//-----------------------------------------------------------------------------------------------------------------------------------

//        System.out.println("******************post-设置关系:如果关系存在就会删除\n******************");
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        //数据转为map
//        JSONArray array = new JSONArray();
//        array.add("5cb3ed06dde1f");
//        JSONArray array2 = new JSONArray();
//        array2.add("5c90ff4f5b693");
//        get_params.put("instance_ids", array);
//        get_params.put("related_instance_ids", array2);
//
//        String ret = easyops.sendRequest("/cmdb_resource/object/NGINX_SERVICE/relation/_SERVICENODE/set", get_params, "POST");
//        System.out.println(ret);


//        资源模型添加属性：
//        System.out.println("******************添加资源模型属性******************");
//        String objID = "fybtest";
//        Map<String,Object> paramMap = new HashMap<>();
//        Map<String,Object> paramValue = new HashMap<>();
//        paramMap.put("object_id",objID);
//        paramMap.put("id","lgw");
//        paramMap.put("name","李国伟");
//        paramMap.put("value","string:str");
//        String uri = "/cmdb_resource/object/"+objID+"/attr";
//        System.out.print(uri);
//
//        String ret = easyops.sendRequest(uri, paramMap, "POST");
//        System.out.println(ret);


        //        资源模型添加属性：
//        System.out.println("******************添加资源模型关系******************");
//        String objID = "fybtest";
//        Map<String,Object> paramMap = new HashMap<>();
//        Map<String,Object> paramValue = new HashMap<>();
//        paramMap.put("name","fybtest-fybtestB");
//        paramMap.put("left_object_id","fybtest");
//        paramMap.put("left_id","fybtest_id");
//        paramMap.put("left_description","fybtest_desc");
//        paramMap.put("right_object_id","fybtestB");
//        paramMap.put("right_id","fybtestB_desc");
//        paramMap.put("right_description","fybtestB_desc");
//        String uri = "/cmdb_resource/object_relation";
//        System.out.print(uri);
//
//        String ret = easyops.sendRequest(uri, paramMap, "POST");
//        System.out.println(ret);


    }

}
