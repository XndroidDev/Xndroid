package net.xx.xndroid.util;


import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.UnsupportedEncodingException;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLEncoder;
import java.util.Map;


public class HttpJson {

    static {
        System.setProperty("sun.net.client.defaultConnectTimeout", "1200");
        System.setProperty("sun.net.client.defaultReadTimeout", "8000");
    }

    private static String streamToString(InputStream input)
    {
        StringBuffer stringBuffer = new StringBuffer();
        BufferedReader bufferedReader = null;
        char[] buff = new char[64*1024];
        int count;
        try {
            bufferedReader = new BufferedReader(new InputStreamReader(input));
            while ((count = bufferedReader.read(buff)) > 0)
            {
                stringBuffer.append(buff, 0, count);
            }
        } catch (IOException e) {
            e.printStackTrace();
            LogUtil.defaultLogWrite("error","streamToString:" + e.getMessage());
            return "";
        } finally {
            if(bufferedReader != null)
                try {
                    bufferedReader.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
        }
        return stringBuffer.toString();
    }

    public static String post(String url, String encodedData) {
        LogUtil.defaultLogWrite("post", url);
        PrintWriter output = null;
        InputStream input = null;
        try {
            URL realUrl = new URL(url);
            URLConnection connection = realUrl.openConnection();
            connection.setConnectTimeout(1200);
            connection.setReadTimeout(12000);
            connection.setRequestProperty("accept", "*/*");
            connection.setRequestProperty("Referer", "http://127.0.0.1:8085/?module=gae_proxy");
            connection.setRequestProperty("content-type","application/x-www-form-urlencoded");
            connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36");
            connection.setDoOutput(true);
            connection.setDoInput(true);
            connection.connect();
            output = new PrintWriter(connection.getOutputStream());
            output.print(encodedData);
            output.flush();
            input = connection.getInputStream();
            return streamToString(input);
        } catch (Exception e) {
            e.printStackTrace();
            LogUtil.defaultLogWrite("error","post fail:" + e.getMessage());
        }
        finally{
            try{
                if(output!=null)
                    output.close();
                if(input!=null)
                    input.close();
            }
            catch(IOException ex){
                ex.printStackTrace();
            }
        }
        return "";
    }

    public static String post(String url, Map<String,String> args)
    {
        String codedArgs = "";
        for(Map.Entry<String,String> entry: args.entrySet())
        {
            try {
                codedArgs += URLEncoder.encode(entry.getKey(), "UTF-8");
                codedArgs += "=";
                codedArgs += URLEncoder.encode(entry.getValue(), "UTF-8");
                codedArgs += "&";
            } catch (UnsupportedEncodingException e) {
                e.printStackTrace();
                return "";
            }
        }
        return post(url, codedArgs.substring(0,codedArgs.length() - 1));

    }

    public static String get(String urlStr)
    {
        //LogUtil.defaultLogWrite("get", urlStr);
        InputStream input = null;
        try {
            URL url = new URL(urlStr);
            URLConnection connection = url.openConnection();
            connection.setConnectTimeout(1200);
            connection.setReadTimeout(8000);
            connection.setRequestProperty("accept", "*/*");
            connection.setRequestProperty("Referer", "http://127.0.0.1:8085/?module=gae_proxy");
            connection.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.75 Safari/537.36");
            connection.connect();
            input = connection.getInputStream();
            return streamToString(input);
        } catch (Exception e) {
            e.printStackTrace();
            LogUtil.defaultLogWrite("error","get fail:" + e.getMessage() + "url:" + urlStr);
        }finally {
            if(input != null)
                try {
                    if(input != null)
                        input.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
        }
        return "";
    }

    public static JSONObject getJson(String url)
    {
        try {
            JSONObject json = new  JSONObject(HttpJson.get(url));
            return json;
        } catch (JSONException e) {
            e.printStackTrace();
        }
        return null;
    }


}
