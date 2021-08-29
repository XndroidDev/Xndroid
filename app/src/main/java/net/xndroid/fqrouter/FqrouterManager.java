package net.xndroid.fqrouter;


import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.VpnService;
import android.os.Build;
import android.os.IBinder;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;
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
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static android.app.Activity.RESULT_OK;
import static net.xndroid.AppModel.sActivity;
import static net.xndroid.AppModel.sContext;
import static net.xndroid.AppModel.sXndroidFile;

public class FqrouterManager {

    public static final int ASK_VPN_PERMISSION = 101;
    public static boolean sRequestApproved = false;
    private static Process mProcess;
    protected static Messenger sMessenger;
    public static boolean sIsQualified = false;
    public static String sNATType = "UNKNOW";
    public static String sTeredoIP = "UNKNOW";
    public static String sLocalTeredoIP = "UNKNOW";
    public static String sFqrouterInfo = "";
    public static String sOriginIPv6 = null;
    private static int sPort = 2515;
    private static int sProxyMode = 0;
    private static List<String> sProxyList = null;

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

            String proxies = HttpJson.get("http://127.0.0.1:" + sPort +"/proxies");
            if(proxies.isEmpty())
                return false;
            sFqrouterInfo = "";
            Matcher matcherProxy = Pattern.compile("<tr>(.+?)</tr>", Pattern.DOTALL).matcher(proxies);
            while(matcherProxy.find()){
                String proxy = matcherProxy.group(1);
                Matcher matcherField = Pattern.compile(
                        "<button.*?>(.+?)</button>.*?<td.*?>(.+?)</td>.*?<td.*?>(.+?)</td>.*?<td.*?>(.+?)</td>.*?<td.*?>(.+?)</td>"
                        , Pattern.DOTALL).matcher(proxy);
                if(!matcherField.find())
                    continue;
                String proxyTip = "";
                if(proxy.contains("btn-inverse"))
                    continue;
                if(proxy.contains("btn-danger"))
                    proxyTip = "(Died)";
                sFqrouterInfo += "<p>" + matcherField.group(1) + proxyTip
                                + "</p><p style=\"color:#545601\">&emsp &emsp RX &nbsp "
                                + matcherField.group(2).replace(" ", "&nbsp ") + " &emsp &ensp "
                                + matcherField.group(3).replace(" ", "&nbsp ")
                                + "</p><p style=\"color:#015F2E\">&emsp &emsp TX &nbsp "
                                + matcherField.group(4).replace(" ", "&nbsp ") + " &emsp &ensp "
                                + matcherField.group(5).replace(" ", "&nbsp ") + "</p><br />";
            }

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

        sOriginIPv6 = originIPv6();
        // if sOriginIPv6 is null, fqrouter will start the teredo service.
        if(!AppModel.sEnableTeredo){
            sOriginIPv6 = "::";
            LogUtils.i("Teredo disabled by user.");
        }else if(!AppModel.sAutoTeredo){
            if(sOriginIPv6 != null) {
                sOriginIPv6 = null;
                AppModel.showToast(AppModel.sContext.getString(R.string.ORIGIN_IPV6_OK_TIP));
                LogUtils.i("force to use teredo");
            }
        }else {
            if (sOriginIPv6 != null) {
                AppModel.showToast(AppModel.sContext.getString(R.string.available_origin_ipv6));
                LogUtils.i("use origin ipv6 " + sOriginIPv6);
            }
        }

        sProxyMode = AppModel.sPreferences.getInt(AppModel.PRE_PROXY_MODE, 0);
        sProxyList = AppModel.loadPackageList();

        LogUtils.i("proxy mode:" + sProxyMode + " proxy list:" + sProxyList);
    }

    public static void onRequestResult(int resultCode, Activity activity){
        if (resultCode == RESULT_OK) {
            sRequestApproved = true;
            Intent service = new Intent(sContext, SocksVpnService.class);
            service.putExtra("origin_ipv6", sOriginIPv6);
            service.putExtra("proxy_mode", sProxyMode);
            service.putExtra("proxy_list", sProxyList.toArray(new String[0]));
            ServiceConnection serviceConnection = new ServiceConnection() {
                @Override
                public void onServiceConnected(ComponentName name, IBinder service) {
                    FqrouterManager.sMessenger = new Messenger(service);
                }

                @Override
                public void onServiceDisconnected(ComponentName name) {
                    FqrouterManager.sMessenger = null;
                }
            };
            sContext.startService(service);
            sContext.bindService(service, serviceConnection, Context.BIND_AUTO_CREATE);
        } else {
            AppModel.fatalError(sContext.getString(R.string.vpn_reject));
        }
    }

    public static void startVpnService(){

        sRequestApproved = false;
        Intent intent = VpnService.prepare(AppModel.sContext);
        if (intent == null) {
            onRequestResult(RESULT_OK, null);
        } else {
            if(AppModel.sActivity != null)
                sActivity.startActivityForResult(intent, ASK_VPN_PERMISSION);
            else{
                try {
                    AppModel.showToast(AppModel.sContext.getString(R.string.start_vpn));
                    Thread.sleep(15000);
                    onRequestResult(RESULT_OK, null);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }

        }
        while (!sRequestApproved){
            try {
                Thread.sleep(400);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }


    public static String originIPv6(){
        String output = ShellUtils.exec("ip route get 2001:13d2:2801::11");
        if(ShellUtils.stdErr != null || output.contains("error") || output.contains("unreachable"))
            return null;
        if(output.contains("dev tun"))
            return null;
        String regex = "src\\s((\\w|:)+)";
        Pattern pattern = Pattern.compile(regex);
        Matcher matcher = pattern.matcher(output);
        while(matcher.find()){
            String ipv6 = matcher.group(1);
            if(!ipv6.contains(":"))
                continue;
            if(ipv6.startsWith("fe80"))
                continue;
            if(ipv6.startsWith("::"))
                continue;
            return ipv6;
        }
        return null;
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
                PackageManager packageManager = AppModel.sContext.getPackageManager();
                String env_path = sXndroidFile + ":$PATH:" + sXndroidFile + "/fqrouter/wifi-tools";

                if(AppModel.sIsRootMode){
                    String uidList = "";
                    if(sProxyList != null){
                        for(String pkg : sProxyList) {
                            try {
                                ApplicationInfo app = packageManager.getPackageInfo(pkg, 0).applicationInfo;
                                if(app == null) {
                                    LogUtils.w("null applicationInfo of " + pkg);
                                    continue;
                                }
                                uidList += app.uid;
                                uidList += " ";
                            } catch (PackageManager.NameNotFoundException e) {
                                LogUtils.e("get uid of " + pkg + " failed", e);
                            }
                        }
                    }

                    uidList = uidList.trim();

                    cmd = "cd " + sXndroidFile + " \n"
                            + "export PATH=" + env_path + "\n"
                            + "export PROXY_MODE=" + sProxyMode + "\n"
                            + "export PROXY_LIST='" + uidList + "'\n"
//                            + "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/lib64:/vendor/lib:/system/lib64:/system/lib\n"
                            + ((AppModel.sDebug || AppModel.sLastFail) ? "export DEBUG=TRUE\n" : "")
                            + (sOriginIPv6 != null ? "export NO_TEREDO=TRUE\n" : "")
                            + (!AppModel.sEnableFqDNS ? "export NO_FQDNS=TRUE\n" : "")
                            + "sh " + sXndroidFile + "/python/bin"
                            + (Build.VERSION.SDK_INT > 17 ? "/python-launcher.sh " : "/python-launcher-nopie.sh ")
                            + sXndroidFile + "/fqrouter/manager/main.py run "
                            + ((AppModel.sDebug || AppModel.sLastFail) ? (" > " + sXndroidFile + "/log/fqrouter-output.log 2>&1 \n") : " >/dev/null 2>&1\n")
                            + "exit\n";
                }else {
                    cmd = "cd " + sXndroidFile + " \n"
                            + "export PATH=" + env_path + "\n"
//                            + "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/lib64:/vendor/lib:/system/lib64:/system/lib\n"
                            + ((AppModel.sDebug || AppModel.sLastFail) ? "export DEBUG=TRUE\n" : "")
                            + (sOriginIPv6 != null ? "export NO_TEREDO=TRUE\n" : "")
                            + (!AppModel.sEnableFqDNS ? "export NO_FQDNS=TRUE\n" : "")
                            + "sh " + sXndroidFile + "/python/bin"
                            + (Build.VERSION.SDK_INT > 17 ? "/python-launcher.sh " : "/python-launcher-nopie.sh ")
                            + sXndroidFile + "/fqrouter/manager/vpn.py "
                            + (Build.VERSION.SDK_INT >= 20 ? " 26.26.26.1 26.26.26.2 " : " 10.25.1.1 10.25.1.2 ")
                            + ((AppModel.sDebug || AppModel.sLastFail) ? (" > " + sXndroidFile + "/log/fqrouter-output.log 2>&1 \n") : " >/dev/null 2>&1\n")
                            + "exit\n";
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
                    LogUtils.e("fqrouter process error ", e);
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
                        LogUtils.e("watch fqrouter fail ", e);
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
            if(null != sMessenger){
                try {
                    sMessenger.send(Message.obtain(null, SocksVpnService.MSG_STOP_VPN, 0, 0));
                } catch (RemoteException e) {
                    e.printStackTrace();
                }
            }
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

            ShellUtils.execBusybox("rm " + sXndroidFile + "/log/fqrouter-output.log");
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
