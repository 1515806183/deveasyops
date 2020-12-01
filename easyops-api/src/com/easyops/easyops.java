package com.easyops;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.security.*;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import java.io.IOException;
import javax.crypto.spec.SecretKeySpec;

import com.alibaba.fastjson.JSON;
import org.apache.commons.codec.binary.Hex;

import net.sf.json.JSONObject;


/**
 * 用于模拟HTTP请求中GET/POST/PUT方式
 * author : July
 */

class EasyOps {

    private Map<String, String> headers;
    private String host;
    private String ACCESS_KEY;
    private String SECRET_KEY;

    public static void main(String[] args) {
        EasyOps easyops = new EasyOps("28.163.0.123", "bada5e73756d30d9a7b5a47a",
                "a81a31823a14eb79d7ca5ead1e12c7ff6e43e472fe6c6ec03913af637565845e");

//        System.out.println("******************GET******************");
//        Map<String, Object> get_params = new HashMap<String, Object>();
//        get_params.put("page_size", "1");
//        get_params.put("page", "1");
//        String ret = easyops.sendRequest("/cmdb/object/instance/list/Users", get_params, "GET");
//        System.out.println(ret);
//        System.out.println("******************END******************\n");

        System.out.println("******************POST******************");
        Map<String, Object> post_params = new HashMap<String, Object>();
        post_params.put("page", "1");
        post_params.put("page_size", "2000");
//        post_params.put("only_relation_view", true);
//        post_params.put("only_my_instance", false);
        Map<String, Object> all_users_param_fields = new HashMap<String, Object>();
        all_users_param_fields.put("instanceId", 1);
        all_users_param_fields.put("name", 1);
        all_users_param_fields.put("_businesses_APP.owner", 1);
        all_users_param_fields.put("_businesses_APP.tester", 1);
        all_users_param_fields.put("_businesses_APP.name_chineses", 1);
        all_users_param_fields.put("_businesses_APP.name", 1);
        all_users_param_fields.put("_businesses_APP.instanceId", 1);
        post_params.put("fields", all_users_param_fields);

        Map<String, Object> query = new HashMap<String, Object>();
        query.put("name", "研究所");
        post_params.put("query", query);

        System.out.println(post_params);
        System.out.println("----------------");

        String ret2 = easyops.sendRequest("/cmdb_resource/object/BUSINESS/instance/_search", post_params, "POST");
        System.out.println(ret2);
        System.out.println("******************END******************\n");

//        System.out.println("******************添加防火墙策略******************");
//        Map<String, Object> map1 = new HashMap<String, Object>();
//        map1.put("name", "策略13");
//        String ret1 = easyops.sendRequest("/cmdb/object/firewallpolicy/instance", map1, "POST");
//        System.out.println(ret1);
//        System.out.println("******************END******************\n");
//
//        System.out.println("******************删除两个实例之间指定的一种关系******************");
//        Map<String, Object> map2 = new HashMap<String, Object>();
//        map2.put("relation_id", "TEST_PACKAGE_TEST_PACKAGE");
//        map2.put("left_instance_id", "5b98905213bde");
//        map2.put("right_instance_id", "5ba214e966d9a");
//        String del_ret = easyops.sendRequest("/cmdb_resource/object_relation/TEST_PACKAGE_TEST_PACKAGE/relation_instance", map2, "DELETE");
//        System.out.println(del_ret);
//        System.out.println("******************END******************\n");
    }

    /**
     * 初始化
     *
     * @param host       服务器IP
     * @param access_key ACCESS——KEY
     * @param secret_key SECRET-KEY
     */
    public EasyOps(String host, String access_key, String secret_key) {
        Map<String, String> hd = new TreeMap<String, String>();
        hd.put("Host", "openapi.easyops-only.com");
        hd.put("Content-Type", "application/json");
        this.headers = hd;
        this.host = host;
        this.ACCESS_KEY = access_key;
        this.SECRET_KEY = secret_key;
    }

    /**
     * 发送GET / DELETE请求
     *
     * @param url        请求URL
     * @param parameters 请求参数
     * @param method     请求方式 GET / DELETE
     * @return String
     */
    private String sendGetAndDel(String url, Map<String, String> parameters, String method) {
        String result = "";
        BufferedReader in = null;// 读取响应输入流
        StringBuffer sb = new StringBuffer();// 存储参数
        String params = "";// 编码之后的参数
        int timeout = 60000;
        System.setProperty("sun.net.http.allowRestrictedHeaders", "true");
        try {
            // 编码请求参数
            if ((parameters != null) && (parameters.size() != 0)) {
                if (parameters.size() == 1) {
                    for (String name : parameters.keySet()) {
                        sb.append(name).append("=").append(
                                java.net.URLEncoder.encode(parameters.get(name),
                                        "UTF-8"));
                    }
                    params = sb.toString();
                } else {
                    for (String name : parameters.keySet()) {
                        sb.append(name).append("=").append(
                                java.net.URLEncoder.encode(parameters.get(name),
                                        "UTF-8")).append("&");
                    }
                    String temp_params = sb.toString();
                    params = temp_params.substring(0, temp_params.length() - 1);
                }
            }
            String full_url = url + (params == "" ? "" : ("?" + params));
            // 创建URL对象
            java.net.URL connURL = new java.net.URL(full_url);
            // 打开URL连接
            java.net.HttpURLConnection httpConn = (java.net.HttpURLConnection) connURL
                    .openConnection();
            httpConn.setConnectTimeout(timeout);
            // 设置通用属性
            httpConn.setRequestProperty("Accept", "*/*");
            httpConn.setRequestProperty("Connection", "Keep-Alive");
            httpConn.setRequestProperty("User-Agent", "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1)");
            for (Object hd : this.headers.keySet()) {
                httpConn.setRequestProperty(hd.toString(), this.headers.get(hd.toString()));
            }
            //设置请求方式
            httpConn.setRequestMethod(method);
            // 建立实际的连接
            httpConn.connect();
            //响应头部获取
            //Map<String, List<String>> headers = httpConn.getHeaderFields();
            //遍历所有的响应头字段
            //for (String key : headers.keySet()) {
            //System.out.println(key + "\t：\t" + headers.get(key));
            //}
            // 定义BufferedReader输入流来读取URL的响应,并设置编码方式
            in = new BufferedReader(new InputStreamReader(httpConn.getInputStream(), "UTF-8"));
            String line;
            // 读取返回的内容
            while ((line = in.readLine()) != null) {
                result += line;
            }
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try {
                if (in != null) {
                    in.close();
                }
            } catch (IOException ex) {
                ex.printStackTrace();
            }
        }
        return result;
    }

    /**
     * 发送POST / PUT请求
     *
     * @param url        请求URL
     * @param parameters 请求参数
     * @param method     请求方式 PUT / POST
     * @return String
     */
    private String sendPostAndPut(String url, Map<String, Object> parameters, String method) {
        String result = "";// 返回的结果
        BufferedReader in = null;// 读取响应输入流
        PrintWriter out = null;
        int timeout = 60000;
        System.setProperty("sun.net.http.allowRestrictedHeaders", "true");
        try {
            // 创建URL对象
            java.net.URL connURL = new java.net.URL(url);
            // 打开URL连接
            java.net.HttpURLConnection httpConn = (java.net.HttpURLConnection) connURL
                    .openConnection();
            httpConn.setConnectTimeout(timeout);
            // 设置通用属性
            httpConn.setRequestProperty("Accept", "*/*");
            httpConn.setRequestProperty("Connection", "Keep-Alive");
            httpConn.setRequestProperty("User-Agent", "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1)");
            for (Object hd : this.headers.keySet()) {
                httpConn.setRequestProperty(hd.toString(), this.headers.get(hd.toString()));
            }
            // 设置POST方式
            httpConn.setRequestMethod(method);
            httpConn.setUseCaches(false);
            httpConn.setDoInput(true);
            httpConn.setDoOutput(true);
            // 获取HttpURLConnection对象对应的输出流
            out = new PrintWriter(httpConn.getOutputStream());
            // 发送请求参数
            out.write(JSONObject.fromObject(parameters).toString());
            // flush输出流的缓冲
            out.flush();
            // 定义BufferedReader输入流来读取URL的响应，设置编码方式
            in = new BufferedReader(new InputStreamReader(httpConn.getInputStream(), "UTF-8"));
            String line;
            // 读取返回的内容
            while ((line = in.readLine()) != null) {
                result += line;
            }
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            try {
                if (out != null) {
                    out.close();
                }
                if (in != null) {
                    in.close();
                }
            } catch (IOException ex) {
                ex.printStackTrace();
            }
        }
        return result;
    }

    /**
     * 使用 Map按key进行排序
     *
     * @param map 排序MAP
     * @return sortMap
     */
    private static Map<String, Object> sortMapByKey(Map<String, Object> map) {
        if (map == null || map.isEmpty()) {
            return null;
        }

        Map<String, Object> sortMap = new TreeMap<String, Object>(new MapKeyComparator());

        sortMap.putAll(map);

        return sortMap;
    }

    /**
     * HASH算法加密
     *
     * @param encryptText 加密文本
     * @param encryptKey  加密算法
     * @return String
     */
    private static String HmacSHA1Encrypt(String encryptText, String encryptKey) {
        byte[] data = encryptKey.getBytes();
        SecretKey secretKey = new SecretKeySpec(data, "HmacSHA1");
        try {
            Mac mac = Mac.getInstance("HmacSHA1");
            mac.init(secretKey);
            byte[] text = encryptText.getBytes();
            return Hex.encodeHexString(mac.doFinal(text));
        } catch (Exception ex) {
            return null;
        }
    }

    /***
     * 生成签名字段
     * @param uri 请求路径
     * @param request_time 请求时间戳
     * @param data 请求数据
     * @param method 请求方法
     * @return signature
     */
    private String genSignature(String uri, long request_time, Map<String, Object> data, String method) {

        String url_params = "";
        String str_sign = "";
        String signature = "";
        //body data md5sum
        String body_content = "";
        //GET做
        if (("GET".equals(method) || "DELETE".equals(method)) && !data.isEmpty()) {
            data = sortMapByKey(data);
            for (Object key : data.keySet()) {
                url_params = url_params + key + data.get(key.toString());
            }
        }

        //POST PUT做body数据的md5sum
        if (("POST".equals(method) || "PUT".equals(method)) && !data.isEmpty()) {
            JSONObject json = JSONObject.fromObject(data);
            String body = json.toString();
            body_content = MD5(body, "UTF-8").toLowerCase();
        }

        str_sign = method + "\n" + uri + "\n" + url_params + "\n" +
                this.headers.get("Content-Type") + "\n" + body_content + "\n" +
                request_time + "\n" + this.ACCESS_KEY;
        System.out.println("************* SIGN *************");
        System.out.println(str_sign);
        System.out.println("********************************");
        signature = HmacSHA1Encrypt(str_sign, this.SECRET_KEY);
        return signature;
    }

    /**
     * 设置请求，所有OPENAPI从这里走请求
     *
     * @param uri        请求URI
     * @param parameters 请求参数
     * @param method     请求方法
     * @return ret
     */
    public String sendRequest(String uri, Map<String, Object> parameters, String method) {
        if (parameters == null) {
            parameters = new HashMap<String, Object>();
        }
        long request_time = System.currentTimeMillis() / 1000L;
        String signature = this.genSignature(uri, request_time, parameters, method);
        String request_url = "http://" + this.host + uri;
        String ret = "";

        if ("GET".equals(method) || "DELETE".equals(method)) {
            parameters.put("accesskey", this.ACCESS_KEY);
            parameters.put("signature", signature);
            parameters.put("expires", request_time + "");

            Map<String, String> mapNew = new HashMap<String, String>();
            for (String string : parameters.keySet()) {
                mapNew.put(string, parameters.get(string).toString());
            }
            ret = sendGetAndDel(request_url, mapNew, method);
        } else {
            request_url += "?accesskey=" + this.ACCESS_KEY + "&signature=" + signature + "&expires=" + request_time + "";
            ret = sendPostAndPut(request_url, parameters, method);
        }
        return ret;
    }

    /**
     * 转MD5 防止中文乱码问题
     *
     * @param s            指定字符串
     * @param encodingType 指定编码
     * @return String
     */
    private static String MD5(String s, String encodingType) {
        char hexDigits[] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'};

        try {
            // 按照相应编码格式获取byte[]
            byte[] btInput = s.getBytes(encodingType);
            // 获得MD5摘要算法的 MessageDigest 对象
            MessageDigest mdInst = MessageDigest.getInstance("MD5");
            // 使用指定的字节更新摘要
            mdInst.update(btInput);
            // 获得密文
            byte[] md = mdInst.digest();
            // 把密文转换成十六进制的字符串形式

            int j = md.length;
            char str[] = new char[j * 2];
            int k = 0;

            for (int i = 0; i < j; i++) {
                byte byte0 = md[i];
                str[k++] = hexDigits[byte0 >>> 4 & 0xf];
                str[k++] = hexDigits[byte0 & 0xf];
            }
            return new String(str);
        } catch (Exception e) {
            return "-1";
        }
    }

    /**
     * 查询指定模型的所有数据
     *
     * @param objectId   模型ID
     * @param parameters 参数
     * @return List<Object>
     */
    public List<Object> sendPostWithAll(String objectId, Map<String, Object> parameters) {
        if (parameters == null) {
            parameters = new HashMap<String, Object>();
        }
        int page = 1;
        int page_size = 300;  // 默认覆盖300条数据一页
        parameters.put("page", page);
        parameters.put("page_size", page_size);

        List<Object> return_data = new ArrayList<Object>();
        while (true) {
            String all_instances_string = this.sendRequest("/cmdb_resource/object/" + objectId + "/instance/_search", parameters, "POST");
            Map all_instances_map = (Map) JSON.parse(all_instances_string);
            Map all_instances_data_map = (Map) all_instances_map.get("data");
            int ret_total = (Integer) all_instances_data_map.get("total");
            List ret_list = (List) all_instances_data_map.get("list");
            return_data.addAll(ret_list);

            if (ret_list.size() < (Integer) parameters.get("page_size")) {
                break;
            }
            if (return_data.size() < ret_total) {
                parameters.put("page", (Integer) parameters.get("page") + 1);
            } else {
                break;
            }
        }

        return return_data;
    }

}

/**
 * MAP按照key排序的比较器
 */
class MapKeyComparator implements Comparator<String> {

    @Override
    public int compare(String str1, String str2) {
        return str1.compareTo(str2);
    }
}
