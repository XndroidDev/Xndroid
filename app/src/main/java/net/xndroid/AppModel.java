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

public class AppModel {
    public static String sAppPath;
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

    public static boolean sDebug = false;
    public static boolean sLastFail = false;

    public static SharedPreferences sPreferences;
    public static boolean sAutoThread = true;
    public static final String PER_AUTO_THREAD = "XNDROID_AUTO_THREAD";
    public static final String PER_VERSION = "XNDROID_VERSION";
    public static final String PER_LAST_FAIL = "XNDROID_LAST_FAIL";

    public static void showToast(final String msg) {
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
    }

    public static void exportLogs(){
        ShellUtils.execBusybox("tar -czf /sdcard/xndroid-logs.tar.gz log/ fqrouter/log/");
    }

    public static void forceStop(){
//        android.os.Process.killProcess(android.os.Process.myPid());

        String cmd = "busybox ps |busybox grep net.xndroid | busybox cut -c 1-6 |busybox xargs kill -9";
        cmd = cmd.replace("busybox", ShellUtils.sBusyBox );
        ShellUtils.exec(cmd);
    }


    public static void fatalError(final String msg){
        LogUtils.e("FatalError: " + msg);
        exportLogs();

        if(sActivity != null) {
            sActivity.runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    new AlertDialog.Builder(AppModel.sActivity)
                            .setTitle("FatalError")
                            .setMessage(msg + "\n\nlogs will be exported to /sdcard/xndroid-logs.tar.gz")
                            .setNegativeButton("exit", new DialogInterface.OnClickListener() {
                                @Override
                                public void onClick(DialogInterface dialog, int which) {
                                    forceStop();
                                }
                            }).create().show();
                }
            });
        }else{
            showToast("FatalError: " + msg + "   logs will be exported to /sdcard/xndroid-logs.tar.gz");
            forceStop();
        }
        while (true){
            try {
                Thread.sleep(1000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
    }



    private static boolean isApkInDebug(Context context) {
        try {
            ApplicationInfo info = context.getApplicationInfo();
            return (info.flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        } catch (Exception e) {
            return false;
        }
    }


    public static boolean sAppStoped = false;
    public static void appStop(){
        if(sAppStoped)
            return;
        sAppStoped = true;
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
//                XXnetService service = XXnetService.getDefaultService();
//                if(service != null)
//                    service.postStop();
                LogUtils.i("appStop");
                LaunchService.postStop();
                forceStop();
            }
        }).start();

    }


    public static boolean sDevBatteryLow = false;
    public static boolean sDevMobileWork = false;
    public static boolean sDevScreenOff = false;
    public static boolean sIsForeground = true;

    public static void checkNetwork(){
        sDevMobileWork = false;
        ConnectivityManager connectivityManager = (ConnectivityManager)AppModel
                .sActivity.getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo activeNetworkInfo = connectivityManager.getActiveNetworkInfo();
        if (activeNetworkInfo != null && activeNetworkInfo.isConnected()) {
            if (activeNetworkInfo.getType() == (ConnectivityManager.TYPE_MOBILE)) {
                sDevMobileWork = true;
            }
        }
        LogUtils.i("network change, use_mobile_network=" + AppModel.sDevMobileWork);
    }

    private static void updataEnv(int lastVersion){

    }


    public static void appInit(final MainActivity activity){
        if(sAppStoped)
            return;
        sAppStoped = false;
        sActivity = activity;
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
