package net.xx.xndroid.xxnet;

import net.xx.xndroid.R;
import net.xx.xndroid.util.HttpJson;
import net.xx.xndroid.util.LogUtil;
import net.xx.xndroid.util.ShellUtil;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.HashMap;
import java.util.Map;

import static net.xx.xndroid.AppModel.sActivity;
import static net.xx.xndroid.AppModel.sXndroidFile;
import static net.xx.xndroid.AppModel.showToast;

public class XXnetAttribute {
    public static String sAppid = " ";
    public static int sIpNum = -1;
    public static int sIpQuality = -1;
    public static String sNetState = "getting information";
    public static boolean sIpv6 = false;
    public static String sXXversion = "";
    public static int sWorkerH1 = 0;
    public static int sWorkerH2 = 0;
    public static boolean sLastupdateOK = false;
    private static int sThreadNum = -1;

    public static String sStateSummary = sActivity.getString(R.string.initializing);
    public static final int SUMMARY_LEVEL_OK = 0;
    public static final int SUMMARY_LEVEL_WARNING = 1;
    public static final int SUMMARY_LEVEL_ERROR = 2;
    public static int sSummaryLevel = SUMMARY_LEVEL_OK;


    private static boolean checkNetwork(){
        String url = "https://www.baidu.com/duty/copyright.html";
        String response = HttpJson.get(url);
        if(response.length() > 0)
            return true;
        else{
            if(HttpJson.get(url).length() > 0)
                return true;
            return false;
        }
    }

// 可能因为联网权限导致无法连接网络,却可以ping通
//    private static boolean checkNetwork(){
//        String res = ShellUtil.execBusybox("timeout -t 4 ping -c 3 114.114.114.114 |" +
//                AppModel.sXndroidFile + "/busybox grep 'time='");
//        if(res.length() > 5)
//            return true;
//        return false;
//    }


    private static int sFailTime = 0;
    private static final int RETRY_TIME = 5;
    public static boolean updateState()
    {
        if(undateAttribute()){
            sFailTime = 0;
            if(!XXnetAttribute.sNetState.equals("OK")){
                sStateSummary = sActivity.getString(R.string.no_internet);
                sSummaryLevel = SUMMARY_LEVEL_ERROR;
            }else if(XXnetAttribute.sIpQuality > 1400) {
                sSummaryLevel = SUMMARY_LEVEL_WARNING;
                sStateSummary = sActivity.getString(R.string.no_ip);
            }else if(sWorkerH2 == 0 && sWorkerH1 ==0){
                sStateSummary = sActivity.getString(R.string.connect_no_establish);
                sSummaryLevel = SUMMARY_LEVEL_WARNING;
            } else {
                sSummaryLevel = SUMMARY_LEVEL_OK;
                sStateSummary = sActivity.getString(R.string.running_normally);
            }
            return true;
        }else if(!checkNetwork()){
            sStateSummary = sActivity.getString(R.string.no_internet);;
            sSummaryLevel = SUMMARY_LEVEL_ERROR;
            return false;
        } else
        {
            if(++sFailTime >= RETRY_TIME){
                sStateSummary = sActivity.getString(R.string.no_respond);
                sSummaryLevel = SUMMARY_LEVEL_ERROR;
            }else {
                sStateSummary = sActivity.getString(R.string.waitting_respond);
                sSummaryLevel = SUMMARY_LEVEL_WARNING;
            }

        }
        return false;
    }


    public static boolean quit(){
        String response = HttpJson.get("http://127.0.0.1:8085/quit");
        if(response.indexOf("success") > 0)
            return true;
        return false;
    }


    private static boolean undateAttribute()
    {
        sLastupdateOK = false;
        JSONObject json = HttpJson.getJson("http://127.0.0.1:8085/module/gae_proxy/control/status");
        if(json == null) {
            LogUtil.defaultLogWrite("warning","get json fail.");
            return false;
        }
        try {
            sAppid = json.getString("gae_appid");
            sIpNum = json.getInt("good_ip_num");
            sIpQuality = json.getInt("ip_quality");
            sNetState = json.getString("network_state");
            sIpv6 = json.getInt("use_ipv6") != 0;
            sXXversion = json.getString("xxnet_version").replace("\n", "");
            sWorkerH1 = json.getInt("worker_h1");
            sWorkerH2 = json.getInt("worker_h2");
//            LogUtil.defaultLogWrite("info", "xxnet state refreshed: Appid=" + sAppid
//            + ",good_ip=" + sIpNum + ",ip_quality=" + sIpQuality + ",net_state="
//            + sNetState + ",ipv6=" + sIpv6 + ",xxnet_version=" + sXXversion);
            sLastupdateOK = true;
            return true;
        } catch (JSONException e) {
            e.printStackTrace();
        }
        return false;
    }


    private static String sIpRange;
    public static boolean setThreadNum(int threadNum)
    {
        if(threadNum == sThreadNum)
            return true;
        LogUtil.defaultLogWrite("info", "setThreadNum:" + threadNum);
        if(sIpRange == null || sIpRange.length() < 6)
            sIpRange = HttpJson.get("http://127.0.0.1:8085/module/gae_proxy/control/scan_ip?cmd=get_range");
        if(sIpRange.length() < 6)
            return false;
        Map<String,String> map = new HashMap<>();
        map.put("auto_adjust_scan_ip_thread_num","1");
        map.put("scan_ip_thread_num","" + threadNum);
        map.put("ip_range",sIpRange);
        String response = HttpJson.post("http://127.0.0.1:8085/module/gae_proxy/control/scan_ip?cmd=update",map);
        if(response.indexOf("success") > 0){
            sThreadNum = threadNum;
            return true;
        }
        LogUtil.defaultLogWrite("error", "setThreadNum fail!");
        return false;
    }


    public static boolean setAppid(String appid)
    {
        if(appid == null)
            return false;
        Map<String,String> map = new HashMap<>();
        map.put("appid",appid);
        map.put("host_appengine_mode","direct");
        map.put("use_ipv6",sIpv6 ? "1" : "0");
        map.put("proxy_enable","0");
        map.put("proxy_type","HTTP");
        map.put("proxy_port","0");
        map.put("proxy_host","");
        map.put("proxy_passwd","");
        map.put("proxy_user","");
        String response = HttpJson.post("http://127.0.0.1:8085/module/gae_proxy/control/config?cmd=set_config",map);
        if(response.indexOf("success") > 0)
            return true;
        return false;
    }


    public static void import_ip(String path){
        if(path == null){
            showToast(sActivity.getString(R.string.err_no_file));
        }else if(!path.endsWith("good_ip.txt")){
            showToast(sActivity.getString(R.string.err_file_name));
        }else {
            String destPath = sXndroidFile + "/xxnet/data/gae_proxy/good_ip.txt";
            ShellUtil.execBusybox("cat \"" + path + "\" >" + destPath);
            ShellUtil.execBusybox("chmod 777 " + destPath);
            showToast(sActivity.getString(R.string.import_over));
        }
    }


}
