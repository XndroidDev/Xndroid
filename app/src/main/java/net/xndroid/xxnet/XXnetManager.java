package net.xndroid.xxnet;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.security.KeyChain;

import net.xndroid.AppModel;
import net.xndroid.R;
import net.xndroid.utils.FileUtils;
import net.xndroid.utils.HttpJson;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.HashMap;
import java.util.Map;

import javax.security.auth.x500.X500Principal;

import static net.xndroid.AppModel.sContext;
import static net.xndroid.AppModel.sXndroidFile;
import static net.xndroid.AppModel.showToast;
import static net.xndroid.LaunchService.unzipRawFile;
import static net.xndroid.utils.ShellUtils.execBusybox;

public class XXnetManager {
    public static String sAppid = " ";
    public static int sIpNum = -1;
    public static int sIpQuality = -1;
    public static String sIPV4State = "UNKNOW";
    public static String sIPV6State = "UNKNOW";
    public static String sIpv6 = "force_ipv6";
    public static String sXXversion = "UNKNOW";
    public static int sWorkerH1 = 0;
    public static int sWorkerH2 = 0;
    public static boolean sLastupdateOK = false;
    public static boolean sIsIdle = false;
    private static int sThreadNum = -1;

    public static final int IMPORT_CERT_REQUEST = 102;

    public static String sStateSummary = sContext.getString(R.string.initializing);
    public static final int SUMMARY_LEVEL_OK = 0;
    public static final int SUMMARY_LEVEL_WARNING = 1;
    public static final int SUMMARY_LEVEL_ERROR = 2;
    public static int sSummaryLevel = SUMMARY_LEVEL_OK;

    private static final String PER_CA_MD5 = "XNDROID_CA_MD5";


    private static boolean _networkResult = false;
    public static boolean checkNetwork(){
        _networkResult = false;
        try {
            String[] urls = new String[]{
                    "https://www.baidu.com/duty/copyright.html",
                    "https://www.zhihu.com/",
                    "https://www.taobao.com/tbhome/page/about/home",
                    "http://www.iqiyi.com/common/copyright.html",
                    "http://www.sogou.com"
            };

            for(final String url: urls){
                new Thread(new Runnable() {
                    @Override
                    public void run() {
                        if(HttpJson.get(url, null).length() > 0){
                            _networkResult = true;
                        }
                    }
                }).start();
            }
            for(int i=0;i<20;i++){
                Thread.sleep(200);
                if(_networkResult)
                    return true;
            }
        }catch (Exception e){
            LogUtils.e("checkNetwork fail", e);
        }
        return false;
    }

// 可能因为联网权限导致无法连接网络,却可以ping通
//    private static boolean checkNetwork(){
//        String res = ShellUtils.execBusybox("timeout -t 4 ping -c 3 114.114.114.114 |" +
//                AppModel.sXndroidFile + "/busybox grep 'time='");
//        if(res.length() > 5)
//            return true;
//        return false;
//    }


    private static int sFailTime = 0;
    private static final int RETRY_TIME = 7;
    public static boolean updateState()
    {
        if(updateAttribute()){
            sFailTime = 0;
            if(!XXnetManager.sIPV4State.equals("OK") && !XXnetManager.sIPV6State.equals("OK")){
                if(!checkNetwork()) {
                    sStateSummary = sContext.getString(R.string.no_internet);
                }else {
                    sStateSummary = sContext.getString(R.string.no_ipv6);
                }
                sSummaryLevel = SUMMARY_LEVEL_ERROR;
            }else if(XXnetManager.sIpQuality > 1800) {
                sSummaryLevel = SUMMARY_LEVEL_WARNING;
                sStateSummary = sContext.getString(R.string.no_ip);
            }else if(sWorkerH2 == 0 && sWorkerH1 ==0){
                if(sIsIdle){
                    sStateSummary = sContext.getString(R.string.gae_idle);
                    sSummaryLevel = SUMMARY_LEVEL_OK;
                }else {
                    sStateSummary = sContext.getString(R.string.connect_no_establish);
                    sSummaryLevel = SUMMARY_LEVEL_WARNING;
                }
            } else {
                sSummaryLevel = SUMMARY_LEVEL_OK;
                sStateSummary = sContext.getString(R.string.running_normally);
            }
            return true;
        }else if(!checkNetwork()){
            sStateSummary = sContext.getString(R.string.no_internet);;
            sSummaryLevel = SUMMARY_LEVEL_ERROR;
            return false;
        } else
        {
            if(++sFailTime >= RETRY_TIME){
                sStateSummary = sContext.getString(R.string.no_respond);
                sSummaryLevel = SUMMARY_LEVEL_ERROR;
            }else {
                sStateSummary = sContext.getString(R.string.waitting_respond);
                sSummaryLevel = SUMMARY_LEVEL_WARNING;
            }

        }
        return false;
    }


    public static boolean quit(){
        String response = HttpJson.get("http://127.0.0.1:8085/quit");
        return response.contains("success");
    }


    private static boolean updateAttribute()
    {
        sLastupdateOK = false;
        JSONObject json = HttpJson.getJson("http://127.0.0.1:8085/module/gae_proxy/control/status");
        if(json == null) {
            LogUtils.d("get json fail.");
            return false;
        }
        try {
            sXXversion = json.getString("xxnet_version").trim();
            sAppid = json.getString("gae_appid");
            sIpNum = json.getInt("good_ipv4_num") + json.getInt("good_ipv6_num");
            sIpQuality = json.getInt("ip_quality");
            sIPV4State = json.getString("ipv4_state");
            sIPV6State = json.getString("ipv6_state");
            sIpv6 = json.getString("use_ipv6");
            sWorkerH1 = json.getInt("worker_h1");
            sWorkerH2 = json.getInt("worker_h2");
            sIsIdle = json.getInt("is_idle") != 0;
//            LogUtils.defaultLogWrite("info", "xxnet state refreshed: Appid=" + sAppid
//            + ",good_ip=" + sIpNum + ",ip_quality=" + sIpQuality + ",net_state="
//            + sIPV4State + ",ipv6=" + sIpv6 + ",xxnet_version=" + sXXversion);
            sLastupdateOK = true;
            return true;
        } catch (JSONException e) {
            LogUtils.e("XX-Net update attributes fail ", e);
        }
        return false;
    }


    private static String sIpRange;
    public static boolean setThreadNum(int threadNum)
    {
        if(threadNum == sThreadNum)
            return true;
        if(sIpRange == null || sIpRange.length() < 6)
            sIpRange = HttpJson.get("http://127.0.0.1:8085/module/gae_proxy/control/scan_ip?cmd=get_range");
        if(sIpRange.length() < 6)
            return false;
        LogUtils.i("setThreadNum:" + threadNum);
        Map<String,String> map = new HashMap<>();
        map.put("auto_adjust_scan_ip_thread_num","1");
        map.put("scan_ip_thread_num","" + threadNum);
        map.put("ip_range",sIpRange);
        map.put("use_ipv6",sIpv6);
        String response = HttpJson.post("http://127.0.0.1:8085/module/gae_proxy/control/scan_ip?cmd=update",map);
        if(response.contains("success")){
            sThreadNum = threadNum;
            return true;
        }
        LogUtils.e("setThreadNum fail:\n" + response);
        return false;
    }


    public static boolean setAppId(String appid)
    {
        if(appid == null)
            return false;
        Map<String,String> map = new HashMap<>();
        map.put("appid",appid);
        map.put("host_appengine_mode","direct");
        map.put("use_ipv6",sIpv6);
        map.put("proxy_enable","0");
        map.put("proxy_type","HTTP");
        map.put("proxy_port","0");
        map.put("proxy_host","");
        map.put("proxy_passwd","");
        map.put("proxy_user","");
        String response = HttpJson.post("http://127.0.0.1:8085/module/gae_proxy/control/config?cmd=set_config",map);
        if(response.indexOf("success") > 0)
            return true;
        LogUtils.e("setAppId fail:\n" + response);
        AppModel.showToast(sContext.getString(R.string.set_appid_fail));
        return false;
    }


    public static void importIp(String path){
        if(path == null){
            showToast(sContext.getString(R.string.err_no_file));
        }else if(!path.endsWith("good_ip.txt")){
            showToast(sContext.getString(R.string.err_file_name));
        }else {
            String destPath = sXndroidFile + "/xxnet/data/gae_proxy/good_ip.txt";
            execBusybox("cat \"" + path + "\" >" + destPath);
            execBusybox("chmod 777 " + destPath);
            showToast(sContext.getString(R.string.import_over));
        }
    }

    public static void prepare(){
        String version = ShellUtils.execBusybox("cat " + AppModel.sXndroidFile + "/xxnet/code/version.txt").trim();
        if(FileUtils.exists(sXndroidFile + "/xxnet/code/" + version + "/launcher/start.py"))
            return;
        if(!unzipRawFile(R.raw.xxnet, sXndroidFile))
            AppModel.fatalError("prepare XX-Net fail");
    }

    public static void startXXnet(Context context){
        Intent intent = new Intent(context,XXnetService.class);
        context.startService(intent);
    }

    public static boolean waitReady(){
        for(int i=0;i < 25;i++){
            if(updateAttribute()) {
                autoImportCA();
                return true;
            }
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        AppModel.fatalError(sContext.getString(R.string.xxnet_timeout));
        return false;
    }

    private static void autoImportCA(){
        String certPath = AppModel.sXndroidFile + "/xxnet/data/gae_proxy/CA.crt";
        if(!FileUtils.exists(certPath))
            return;
        String md5 = ShellUtils.execBusybox("md5sum " + certPath + " | " + ShellUtils.sBusyBox + " cut -c 1-32").trim();
        String lastMd5 = AppModel.sPreferences.getString(PER_CA_MD5, "");
        if(lastMd5.isEmpty() || !lastMd5.equals(md5)) {
            if(ShellUtils.isRoot()) {
                importSystemCert();
            }else {
                importCert();
            }
        }

    }

    private static boolean isGoAgentCert(String certPath){
        try {
            X509Certificate cert = (X509Certificate) CertificateFactory
                    .getInstance("X.509").generateCertificate(new FileInputStream(certPath));
            X500Principal subject = cert.getSubjectX500Principal();
            return subject.getName().toLowerCase().contains("goagent");
        }catch (Exception e){
            LogUtils.e("get subject fail", e);
        }
        return false;
    }


    private static String getSubjectHash(String certPath){
        try {
            X509Certificate cert = (X509Certificate) CertificateFactory
                    .getInstance("X.509").generateCertificate(new FileInputStream(certPath));
            X500Principal subject = cert.getSubjectX500Principal();
            byte[] sumbytes = MessageDigest.getInstance("MD5").digest(subject.getEncoded());
            return Integer.toHexString(ByteBuffer.wrap(sumbytes).order(ByteOrder.LITTLE_ENDIAN).getInt());
        }catch (Exception e){
            LogUtils.e("get subject old hash fail", e);
        }
//        return "8da8b1b3";
        return null;
    }

    public static void cleanSystemCert(){
        if(!ShellUtils.isRoot()) {
            AppModel.showToast(sContext.getString(R.string.no_root_no_need));
            return;
        }
        String[] certs = new File("/system/etc/security/cacerts").list();
        if(certs == null){
            AppModel.showToast("cleanSystemCert fail, can't list");
            return;
        }
        int count = 0;
        ShellUtils.execBusybox("mount -o remount,rw /system");
        for(String cert : certs){
            if(isGoAgentCert("/system/etc/security/cacerts/" + cert)){
                ShellUtils.execBusybox("rm /system/etc/security/cacerts/" + cert);
                count ++;
                LogUtils.i("remove system cert " + cert);
            }
        }
        ShellUtils.execBusybox("mount -o remount,ro /system");
        AppModel.showToast(sContext.getString(R.string.finished) + " " + count + "CA");
    }

    public static void importSystemCert() {
        if(!ShellUtils.isRoot()) {
            AppModel.showToast(sContext.getString(R.string.sys_cert_no_root));
            return;
        }
        String certPath = AppModel.sXndroidFile + "/xxnet/data/gae_proxy/CA.crt";
        ShellUtils.execBusybox("chmod 777 " + certPath);
        ShellUtils.execBusybox("cp -f " + certPath + " /sdcard/XX-Net.crt");
        if(!new File(certPath).exists()){
            if(new File("/sdcard/XX-Net.crt").exists()){
                certPath = "/sdcard/XX-Net.crt";
            }else {
                LogUtils.e("importCert fail, file not exist");
                AppModel.showToast("import certificate fail, file not exist");
                return;
            }
        }
        String subjectHash = getSubjectHash(certPath);
        if(subjectHash == null){
            AppModel.showToast("import system certificate fail, get subject old hash fail.");
            return;
        }
        LogUtils.i("subjectHash: " + subjectHash);
        ShellUtils.execBusybox("mount -o remount,rw /system");
        String output = ShellUtils.execBusybox("cp -f " + certPath + " /system/etc/security/cacerts/" + subjectHash + ".0");
        if(output.trim().length() > 0 || ShellUtils.stdErr != null){
            AppModel.showToast(sContext.getString(R.string.system_cert_fail) + " " + output.trim() + " "
                    + (ShellUtils.stdErr!=null ? ShellUtils.stdErr:""));
        }else {
            AppModel.showToast(sContext.getString(R.string.system_cert_succeed) + " " + subjectHash + ".0");
        }
        ShellUtils.execBusybox("chmod 644 /system/etc/security/cacerts/" + subjectHash + ".0");
        ShellUtils.execBusybox("mount -o remount,ro /system");

        String md5 = ShellUtils.execBusybox("md5sum " + certPath + " | " + ShellUtils.sBusyBox + " cut -c 1-32").trim();
        AppModel.sPreferences.edit().putString(PER_CA_MD5, md5).apply();
    }

    public static void importCert(){
//        if(null == AppModel.sActivity) {
//            AppModel.showToast(AppModel.sContext.getString(R.string.reimport_cert_tip));
//            return;
//        }
        String certPath = AppModel.sXndroidFile + "/xxnet/data/gae_proxy/CA.crt";
        ShellUtils.execBusybox("chmod 777 " + certPath);
        ShellUtils.execBusybox("cp -f " + certPath + " /sdcard/XX-Net.crt");
        if(!new File(certPath).exists()){
            if(new File("/sdcard/XX-Net.crt").exists()){
                certPath = "/sdcard/XX-Net.crt";
            }else {
                LogUtils.e("importCert fail, file not exist");
                AppModel.showToast("import certificate fail, file not exist");
                return;
            }
        }
        AppModel.showToast(sContext.getString(R.string.import_cert_tip)
                + (Build.VERSION.SDK_INT>23?( sContext.getString(R.string.import_cert_7tip)):"" ));
        byte[] keychain;
        try{
            BufferedInputStream input =new BufferedInputStream(new FileInputStream(certPath));
            keychain = new byte[input.available()];
            input.read(keychain);
        }catch (Exception e){
            LogUtils.e("read certificate fail!", e);
            return;
        }
        Intent installIntent = KeyChain.createInstallIntent();
        installIntent.putExtra(KeyChain.EXTRA_CERTIFICATE, keychain);
        installIntent.putExtra(KeyChain.EXTRA_NAME,"XX-Net Chain");
        //AppModel.sActivity.startActivityForResult(installIntent, IMPORT_CERT_REQUEST);
        AppModel.sContext.startActivity(installIntent);

        String md5 = ShellUtils.execBusybox("md5sum " + certPath + " | " + ShellUtils.sBusyBox + " cut -c 1-32").trim();
        AppModel.sPreferences.edit().putString(PER_CA_MD5, md5).apply();

    }

    public static boolean updateXXNet(boolean rmdata) {
        String tmpDir = AppModel.sXndroidFile + "/tmp_update_xxnet";
        boolean ret = updateXXNet(rmdata, tmpDir);
        ShellUtils.execBusybox("rm -r " + tmpDir);
        return ret;
    }

    private static boolean updateXXNet(boolean rmdata, String tmpDir) {
        String xxnetZip = "/sdcard/XX-Net.zip";
        if(!new File(xxnetZip).exists()){
            xxnetZip = null;
            String[] files = new File("/sdcard").list();
            if(null != files){
                for(String file : files){
                    if(file.toLowerCase().startsWith("xx-net")
                            && file.toLowerCase().endsWith(".zip")){
                        xxnetZip = "/sdcard/" + file;
                        break;
                    }
                }
            }
            if(null == xxnetZip){
                AppModel.showToast(sContext.getString(R.string.xxnet_zip_no_find));
                return false;
            }
        }
        ShellUtils.execBusybox("rm -r " + tmpDir);
        ShellUtils.execBusybox("mkdir " + tmpDir);
        ShellUtils.execBusybox("unzip " + xxnetZip + " -d " + tmpDir);
        String[] subDirs = ShellUtils.execBusybox("ls " + tmpDir).trim().split("\\s+");
        /* File.list() doesn't work if it's create by root */
        //String[] subDirs = new File(tmpDir).list();
        if(null == subDirs || 0 == subDirs.length){
            AppModel.showToast(sContext.getString(R.string.xxnet_zip_not_complete));
            return false;
        }
        String newXXNet = tmpDir + "/" + subDirs[0];
        String version = ShellUtils.execBusybox("cat " + newXXNet + "/code/default/version.txt").trim();
        if(ShellUtils.stdErr != null || version.length() == 0){
            AppModel.showToast(sContext.getString(R.string.xxnet_zip_unknown_version));
            return false;
        }
        ShellUtils.execBusybox("mv " + newXXNet + "/code/default "
                + AppModel.sXndroidFile + "/xxnet/code/" + version);
        if(ShellUtils.stdErr != null){
            AppModel.showToast(sContext.getString(R.string.update_xxnet_fail));
            return false;
        }
        ShellUtils.execBusybox("echo " + version + " > " + AppModel.sXndroidFile + "/xxnet/code/version.txt");
        String pwd = ShellUtils.execBusybox("pwd").trim();
        ShellUtils.exec("cd " + AppModel.sXndroidFile + "/xxnet/code");
        ShellUtils.execBusybox("rm default");
        ShellUtils.execBusybox("ln -s " + version + " default");
        ShellUtils.exec("cd " + pwd);
        if(rmdata){
            ShellUtils.execBusybox("rm -r " + AppModel.sXndroidFile + "/xxnet/data");
        }
        AppModel.showToast("update XX-Net to " + version + " finished");
        return true;
    }

}
