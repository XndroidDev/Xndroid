package net.xndroid.fqrouter;


import android.app.Activity;
import android.content.Intent;
import android.net.VpnService;
import android.os.Build;
import android.util.Log;

import net.xndroid.AppModel;
import net.xndroid.LaunchService;
import net.xndroid.R;
import net.xndroid.utils.FileUtils;
import net.xndroid.utils.HttpJson;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStreamWriter;
import java.util.HashMap;
import java.util.Map;

import static android.app.Activity.RESULT_OK;
import static net.xndroid.AppModel.sActivity;
import static net.xndroid.AppModel.sContext;
import static net.xndroid.AppModel.sXndroidFile;

public class FqrouterManager {

    public static final int ASK_VPN_PERMISSION = 101;
    public static boolean sRequestApproved = false;
    private static Process mProcess;

    public static boolean sIsQualified = false;
    public static String sNATType = "UNKNOW";
    public static String sTeredoIP = "UNKNOW";
    public static String sLocalTeredoIP = "UNKNOW";
    public static String sFqrouterInfo = "";
    private static int sPort = 2515;

    static {
        sPort = getHttpManagerPort();
    }

    public static int getPort(){
        return sPort;
    }

    public static boolean updateAttribute()
    {
        JSONObject json = HttpJson.getJson("http://127.0.0.1:" + sPort + "/teredo-state");
        if(json == null) {
            LogUtils.d("get json fail.");
            return false;
        }
        try {
            sIsQualified = json.getBoolean("qualified");
            sNATType = json.getString("nat_type");
            sTeredoIP = json.getString("teredo_ip");
            sLocalTeredoIP = json.getString("local_teredo_ip");
            sFqrouterInfo = HttpJson.get("http://127.0.0.1:" + sPort +"/proxies");
            sFqrouterInfo = sFqrouterInfo.replace("</td>", "    </td>");
            sFqrouterInfo = sFqrouterInfo.replace("</tr>", "</tr><br/><br/>");
            return true;
        } catch (JSONException e) {
            LogUtils.e("fqrouter update attributes fail ", e);
        }
        return false;
    }

    public static void prepareFqrouter(){
        String vpnPath = sXndroidFile + "/fqrouter/manager/vpn.py";
        if(!FileUtils.exists(vpnPath)) {
            if (!LaunchService.unzipRawFile(R.raw.fqrouter, sXndroidFile))
                AppModel.fatalError("prepare fqrouter fail");
            if(Build.VERSION.SDK_INT >= 21){
                if(FileUtils.exists(sXndroidFile + "/fqrouter/wifi-tools-pie")){
                    ShellUtils.execBusybox("rm -r " + sXndroidFile + "/fqrouter/wifi-tools");
                    ShellUtils.execBusybox("mv " + sXndroidFile + "/fqrouter/wifi-tools-pie "
                            + sXndroidFile + "/fqrouter/wifi-tools");
                }
            }
        }
    }

    public static void onRequestResult(int resultCode, Activity activity){
        if (resultCode == RESULT_OK) {
            sRequestApproved = true;
            sContext.startService(new Intent(sContext, SocksVpnService.class));
        } else {
            AppModel.fatalError(sContext.getString(R.string.vpn_reject));
        }
    }

    public static void startVpnService(){
//        String[] fds = new File("/proc/self/fd").list();
//        if(fds == null){
//            LogUtils.e("fdtest: fds is null");
//        }else {
//            LogUtils.i("fdtest: fds.length=" + fds.length);
//        }
//        ShellUtils.execBusybox("ls -l /proc/self/fd");
//        try {
//            LogUtils.i("fd CanonicalPath test:\n" + new File("/proc/self/fd/0").getCanonicalPath());
//        }catch (Exception e){
//            LogUtils.e("fd CanonicalPath test fail", e);
//        }

        sRequestApproved = false;
        Intent intent = VpnService.prepare(sActivity);
        if (intent == null) {
            onRequestResult(RESULT_OK, sActivity);
        } else {
            sActivity.startActivityForResult(intent, ASK_VPN_PERMISSION);
        }
        while (!sRequestApproved){
            try {
                Thread.sleep(400);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }


    public static void startFqrouter(){
        new Thread(new Runnable() {
            @Override
            public void run() {
                byte[] output = new byte[1024];
                int readLen = 0;
                byte[] error = new byte[1024];
                int errorLen = 0;
                String cmd = "";
                if(AppModel.sIsRootMode){
                    cmd = "cd " + sXndroidFile + " \n"
                            + "export PATH=" + sXndroidFile + ":$PATH\n"
//                            + "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/lib64:/vendor/lib:/system/lib64:/system/lib\n"
                            + ((AppModel.sDebug || AppModel.sLastFail) ? "export DEBUG=TRUE\n" : "")
                            + "sh " + sXndroidFile + "/python/bin"
                            + (Build.VERSION.SDK_INT > 17 ? "/python-launcher.sh " : "/python-launcher-nopie.sh ")
                            + sXndroidFile + "/fqrouter/manager/main.py run "
                            + " > " + sXndroidFile + "/log/fqrouter-output.log 2>&1 \nexit\n";
                }else {
                    cmd = "cd " + sXndroidFile + " \n"
                            + "export PATH=" + sXndroidFile + ":$PATH\n"
//                            + "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/lib64:/vendor/lib:/system/lib64:/system/lib\n"
                            + ((AppModel.sDebug || AppModel.sLastFail) ? "export DEBUG=TRUE\n" : "")
                            + "sh " + sXndroidFile + "/python/bin"
                            + (Build.VERSION.SDK_INT > 17 ? "/python-launcher.sh " : "/python-launcher-nopie.sh ")
                            + sXndroidFile + "/fqrouter/manager/vpn.py "
                            + (Build.VERSION.SDK_INT >= 20 ? " 26.26.26.1 26.26.26.2 " : " 10.25.1.1 10.25.1.2 ")
                            + " > " + sXndroidFile + "/log/fqrouter-output.log 2>&1 \nexit\n";
                }
                LogUtils.i("try to start fqrouter, cmd: " + cmd);
                try {
                    mProcess = Runtime.getRuntime().exec(ShellUtils.isRoot()?"su":"sh");
                    OutputStreamWriter sInStream = new OutputStreamWriter(mProcess.getOutputStream());
                    sInStream.write(cmd);
                    sInStream.flush();
                    mProcess.waitFor();
                    if(mProcess != null) {
                        readLen = mProcess.getInputStream().read(output);
                        errorLen = mProcess.getErrorStream().read(error);
                    }
                    mProcess = null;
                } catch (Exception e) {
                    e.printStackTrace();
                    AppModel.fatalError("fqrouter process error: " + e.getMessage());
                }
                mProcess = null;
                LogUtils.i("fqrouter exit output :\n" + (readLen <= 0 ? "" : new String(output, 0, readLen)));
                LogUtils.i("fqrouter exit error :\n" + (errorLen <= 0 ? "" : new String(error, 0, errorLen)));
                if(!AppModel.sAppStoped)
                    AppModel.fatalError(sContext.getString(R.string.fqrouter_exit_un));


            }
        }).start();
    }

    private static int getHttpManagerPort() {
        File configFile = new File(sXndroidFile + "/fqrouter/etc/fqsocks.json");
        if (!configFile.exists()) {
            Log.w("xndroid_log", "fqsocks.json don't exist");
            return 2515;
        }
        try {
            FileInputStream input = new FileInputStream(configFile);
            JSONObject json = new JSONObject(HttpJson.streamToString(input));
            return json.getJSONObject("http_manager").getInt("port");
        } catch (Exception e) {
            Log.e("xndroidLog", "failed to parse config", e);
            return 2515;
        }
    }

    private static boolean ping(){
        String content = HttpJson.get("http://127.0.0.1:" + sPort + "/ping");
        if (content.contains("PONG")) {
            LogUtils.i("ping succeeded");
            return true;
        } else {
            LogUtils.d("ping failed: " + content);
            return false;
        }
    }


    private static void watchFqrouter()
    {
        new Thread(new Runnable() {
            @Override
            public void run() {
                while(true)
                {
                    try {
                        if(AppModel.sAppStoped)
                            return;
                        if (AppModel.sUpdateInfoUI != null && sActivity != null) {
                            updateAttribute();
                            sActivity.runOnUiThread(AppModel.sUpdateInfoUI);
                        }

                        if(AppModel.sDevScreenOff || !AppModel.sIsForeground)
                            Thread.sleep(5000);
                        else
                            Thread.sleep(3000);

                    } catch (Exception e) {
                        LogUtils.e("watchFqrouter error ", e);
                    }
                }
            }
        }).start();

    }


    public static boolean waitReady(){
        for(int i=0;i<(AppModel.sIsRootMode?25:20);i++){
            if(ping()) {
                watchFqrouter();
                return true;
            }
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        AppModel.fatalError(sContext.getString(R.string.fqrouter_timeout));
        return false;
    }

    public static boolean quit(){
        String response = HttpJson.post("http://127.0.0.1:" + sPort +"/exit", "");
        return response.contains("EXITING");
    }

    public static void postStop(){
        if(!AppModel.sIsRootMode) {
            sContext.stopService(new Intent(sContext, SocksVpnService.class));
        }
        if(mProcess != null) {
            if (!quit()) {
                Log.e("xndroid_log", "quit fqrouter fail");
                if (mProcess != null) {
                    Log.w("xndroid_log", "destroy fqrouter process");
                    mProcess.destroy();
                }
                mProcess = null;
            }
        }
    }

    public static void cleanIptables(){
        ShellUtils.exec("iptables -t filter --flush fq_FORWARD");
        ShellUtils.exec("iptables -t filter --flush fq_INPUT");
        ShellUtils.exec("iptables -t filter --flush fq_OUTPUT");
        ShellUtils.exec("iptables -t nat --flush fq_INPUT");
        ShellUtils.exec("iptables -t nat --flush fq_OUTPUT");
        ShellUtils.exec("iptables -t nat --flush fq_POSTROUTING");
        ShellUtils.exec("iptables -t nat --flush fq_PREROUTING");
    }

    public static boolean exitFinished(){
        return mProcess == null;
    }

    public static void changeTeredoServer(String ip){
        Map<String, String> map = new HashMap<>();
        map.put("server", ip);
        HttpJson.post("http://127.0.0.1:" + sPort + "/teredo-set-server", map);
    }
}
