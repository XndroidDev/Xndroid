package net.xndroid;


import android.app.AlertDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Looper;
import android.preference.PreferenceManager;
import android.widget.Toast;

import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import java.io.OutputStreamWriter;

public class AppModel {
    public static String sAppPath;
    /*use sActivity carefully, it may be null!*/
    public static MainActivity sActivity;
    public static LaunchService sService;
    public static String sFilePath;
    public static String sXndroidFile;
    public static Runnable sUpdateInfoUI;
    public static String sLang;
    public static String sPackageName;
    public static int sVersionCode;
    public static int sLastVersion;
    public static String sVersionName;
    public static Context sContext;

    public static boolean sDebug = false;
    public static boolean sLastFail = false;

    public static SharedPreferences sPreferences;
    public static boolean sAutoThread = true;
    public static final String PER_AUTO_THREAD = "XNDROID_AUTO_THREAD";
    public static final String PER_VERSION = "XNDROID_VERSION";
    public static final String PER_LAST_FAIL = "XNDROID_LAST_FAIL";

    public static void showToast(final String msg) {
        try {
            if(sActivity != null) {
                sActivity.runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        Toast.makeText(sActivity, msg, Toast.LENGTH_LONG).show();
                    }
                });
                return;
            }
            if(sService != null){
                Looper.prepare();
                Toast.makeText(sService.getApplicationContext(), msg, Toast.LENGTH_LONG).show();
                Looper.loop();
            }
        }catch (Exception e){
            e.printStackTrace();
        }

    }

    public static void exportLogs(){
        ShellUtils.execBusybox("tar -czf /sdcard/xndroid-logs.tar.gz -C " + sXndroidFile + " log/ fqrouter/log/");
        showToast(sContext.getString(R.string.log_exported));
    }

    public static void forceStop(){
        String cmd = "busybox ps |busybox grep net.xndroid | busybox cut -c 1-6 |busybox xargs kill -9";
        cmd = cmd.replace("busybox", sXndroidFile + "/busybox");
        try {
            ShellUtils.exec(cmd);
        }catch (Exception e){
            e.printStackTrace();
            try {
                Process process = Runtime.getRuntime().exec(sXndroidFile + "/busybox sh");
                OutputStreamWriter sInStream = new OutputStreamWriter(process.getOutputStream());
                sInStream.write(cmd);
                sInStream.write('\n');
                sInStream.flush();
                process.waitFor();
            }catch (Exception ee){
                ee.printStackTrace();
                android.os.Process.killProcess(android.os.Process.myPid());
            }
        }

    }


    public static void fatalError(final String msg){
        try {
            LogUtils.e("FatalError: " + msg);
            exportLogs();

            if (sActivity != null) {
                sActivity.runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        new AlertDialog.Builder(AppModel.sActivity)
                                .setTitle(R.string.fatalerror)
                                .setMessage(msg)
                                .setCancelable(false)
                                .setNegativeButton(R.string.exit, new DialogInterface.OnClickListener() {
                                    @Override
                                    public void onClick(DialogInterface dialog, int which) {
                                        forceStop();
                                    }
                                }).create().show();
                    }
                });
            } else {
                showToast(sContext.getString(R.string.fatalerror) + ": " + msg);
                forceStop();
            }
            while (true) {
                try {
                    Thread.sleep(1000);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
        }catch (Exception e){
            e.printStackTrace();
            forceStop();
        }

    }



    private static boolean isApkInDebug(Context context) {
        try {
            ApplicationInfo info = context.getApplicationInfo();
            return (info.flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }
    }


    public static boolean sAppStoped = false;
    public static void appStop(){
        if(sAppStoped)
            return;
        sAppStoped = true;
        try {
            sPreferences.edit().putBoolean(PER_LAST_FAIL, false).commit();
            if(sActivity != null) {
                sActivity.runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        sActivity.postStop();
                    }
                });
            }

            new Thread(new Runnable() {
                @Override
                public void run() {
                    LogUtils.i("appStop");
                    LaunchService.postStop();
                    forceStop();
                }
            }).start();
        }catch (Exception e){
            e.printStackTrace();
            forceStop();
        }


    }


    public static boolean sDevBatteryLow = false;
    public static boolean sDevMobileWork = false;
    public static boolean sDevScreenOff = false;
    public static boolean sIsForeground = true;

    private static ConnectivityManager sConnectivityManager;
    public static void getNetworkState(){
        if(sConnectivityManager == null){
            sConnectivityManager = (ConnectivityManager)sContext.getSystemService(Context.CONNECTIVITY_SERVICE);
        }
        sDevMobileWork = false;
        NetworkInfo activeNetworkInfo = sConnectivityManager.getActiveNetworkInfo();
        if (activeNetworkInfo != null && activeNetworkInfo.isConnected()) {
            if (activeNetworkInfo.getType() == (ConnectivityManager.TYPE_MOBILE)) {
                sDevMobileWork = true;
            }
        }
        LogUtils.i("network change, use_mobile_network=" + sDevMobileWork);
    }

    private static void updataEnv(int lastVersion){

    }


    public static void appInit(final MainActivity activity){
        if(sAppStoped)
            return;
        sAppStoped = false;
        sActivity = activity;
        sContext = activity.getApplicationContext();
        sFilePath = activity.getFilesDir().getAbsolutePath();
        sAppPath = activity.getFilesDir().getParent();
        sXndroidFile = sFilePath + "/xndroid_files";
        sPackageName = activity.getPackageName();
        try {
            sVersionCode = activity.getPackageManager().
                    getPackageInfo(sPackageName, PackageManager.GET_CONFIGURATIONS).versionCode;
            sVersionName = activity.getPackageManager().
                    getPackageInfo(sPackageName, PackageManager.GET_CONFIGURATIONS).versionName;
        } catch (PackageManager.NameNotFoundException e) {
            e.printStackTrace();
        }
        sPreferences = PreferenceManager.getDefaultSharedPreferences(activity);
        sAutoThread = sPreferences.getBoolean(PER_AUTO_THREAD, true);
        sLastVersion = sPreferences.getInt(PER_VERSION, 0);
        sDebug = isApkInDebug(activity);
        sLastFail = sPreferences.getBoolean(PER_LAST_FAIL, false);
        sPreferences.edit().putBoolean(PER_LAST_FAIL, true).apply();
        if(sVersionCode != sLastVersion && sLastVersion != 0)
            updataEnv(sLastVersion);
        sPreferences.edit().putInt(PER_VERSION, sVersionCode).apply();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            sLang = sActivity.getResources().getConfiguration().getLocales().toString();
        }else {
            sLang = sActivity.getResources().getConfiguration().locale.toString();
        }

        Intent intent = new Intent(activity,LaunchService.class);
        activity.startService(intent);
    }
}
