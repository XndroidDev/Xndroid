package net.xndroid.fqrouter;


import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.VpnService;
import android.os.Build;

import net.xndroid.AppModel;
import net.xndroid.LaunchService;
import net.xndroid.R;
import net.xndroid.utils.HttpJson;
import net.xndroid.utils.LogUtils;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.OutputStreamWriter;

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

    public static boolean updateAttribute()
    {
        JSONObject json = HttpJson.getJson("http://127.0.0.1:2515/teredo-state");
        if(json == null) {
            LogUtils.d("get json fail.");
            return false;
        }
        try {
            sIsQualified = json.getBoolean("qualified");
            sNATType = json.getString("nat_type");
            sTeredoIP = json.getString("teredo_ip");
            sLocalTeredoIP = json.getString("local_teredo_ip");
            sFqrouterInfo = HttpJson.get("http://127.0.0.1:2515/proxies");
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
        if(!new File(vpnPath).exists())
            if(!LaunchService.unzipRawFile(R.raw.fqrouter, sXndroidFile))
                AppModel.fatalError("prepare fqrouter fail");
    }

    public static void onRequestResult(int resultCode, Activity activity){
        if (resultCode == RESULT_OK) {
            sRequestApproved = true;
            activity.startService(new Intent(activity, SocksVpnService.class));
        } else {
            AppModel.fatalError(sContext.getString(R.string.vpn_reject));
        }
    }

    private static String _startVpnService(){
        String[] fds = new File("/proc/self/fd").list();
        if (null == fds) {
            return  "failed to list /proc/self/fd";
        }
        if (fds.length > 500) {
            return  "too many fds before start: " + fds.length;
        }
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
        return null;
    }

    public static void startVpnService(){
        String err = _startVpnService();
        if(err != null){
            AppModel.fatalError("start fqrouter fail: " + err);
        }
    }


    public static void startFqrouter(){
        new Thread(new Runnable() {
            @Override
            public void run() {
                String cmd = "cd " + sXndroidFile + " \n" +
                        ((AppModel.sDebug || AppModel.sLastFail)?"export DEBUG=TRUE\n":"") +
                        sXndroidFile + "/python/bin" +
                        (Build.VERSION.SDK_INT >=19?"/python-launcher.sh ":"python-launcher-nopie.sh ") +
                        sXndroidFile + "/fqrouter/manager/vpn.py " +
                        (Build.VERSION.SDK_INT >= 20?" 26.26.26.1 26.26.26.2 ":" 10.25.1.1 10.25.1.2 ") +
                        " > " + sXndroidFile + "/log/fqrouter-output.log 2>&1 \nexit\n";
                LogUtils.i("try to start fqrouter, cmd: " + cmd);
                try {
                    mProcess = Runtime.getRuntime().exec(sXndroidFile + "/busybox sh");
                    OutputStreamWriter sInStream = new OutputStreamWriter(mProcess.getOutputStream());
                    sInStream.write(cmd);
                    sInStream.flush();
                    mProcess.waitFor();
                } catch (Exception e) {
                    e.printStackTrace();
                    AppModel.fatalError("fqrouter process error: " + e.getMessage());
                }
                mProcess = null;
                LogUtils.i("fqrouter exit.");
                if(!AppModel.sAppStoped)
                    AppModel.fatalError(sContext.getString(R.string.fqrouter_exit_un));


            }
        }).start();
    }

//    private static int getHttpManagerPort() {
//        File configFile = new File(sXndroidFile + "/fqrouter/etc/fqsocks.json");
//        if (!configFile.exists()) {
//            return 2515;
//        }
//        try {
//            FileInputStream input = new FileInputStream(configFile);
//            JSONObject json = new JSONObject(HttpJson.streamToString(input));
//            return json.getInt("port");
//        } catch (Exception e) {
//            LogUtils.e("failed to parse config", e);
//            return 2515;
//        }
//    }

    private static boolean ping(){
        String content = HttpJson.get("http://127.0.0.1:2515/ping");
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
                            Thread.sleep(8000);
                        else
                            Thread.sleep(4000);

                    } catch (Exception e) {
                        LogUtils.e("watchFqrouter error ", e);
                    }
                }
            }
        }).start();

    }


    public static boolean waitReady(){
        for(int i=0;i<15;i++){
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

    private static boolean quit(){
        String response = HttpJson.post("http://127.0.0.1:2515/exit", "");
        return response.contains("EXITING");
    }

    public static void postStop(){
        Context context = AppModel.sService;
        context.stopService(new Intent(context, SocksVpnService.class));
        if(mProcess != null)
            if(!quit()) {
                if(mProcess != null) {
                    mProcess.destroy();
                }
                mProcess = null;
            }
    }

    public static boolean exitFinished(){
        return mProcess == null;
    }

}
