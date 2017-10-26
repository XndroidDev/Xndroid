package net.xx.xndroid;


import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.preference.PreferenceManager;
import android.widget.Toast;

import net.xx.xndroid.util.LogUtil;

public class AppModel {
    public static String sAppPath;
    public static MainActivity sActivity;
    public static String sFilePath;
    public static String sXndroidFile;
    public static Runnable sUpdateInfoUI;
    public static String sLang;
    public static String sPackageName;
    public static int sVersionCode;
    public static String sVersionName;

    public static SharedPreferences sPreferences;
    public static boolean sAutoThread = true;
    public static final String PER_AUTO_THREAD = "XNDROID_AUTO_THREAD";
    public static final String PER_VERSION = "XNDROID_VERSION";


    public static void showToast(final String mesg) {
        sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                Toast.makeText(sActivity, mesg, Toast.LENGTH_LONG).show();
            }
        });
    }


    public static boolean sAppStoped = false;
    public static void appStop(){
        if(sAppStoped)
            return;
        sAppStoped = true;
        sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                sActivity.postStop();
            }
        });
        new Thread(new Runnable() {
            @Override
            public void run() {
                XXnetService service = XXnetService.getDefaultService();
                if(service != null)
                    service.postStop();
                android.os.Process.killProcess(android.os.Process.myPid());

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
        LogUtil.defaultLogWrite("info", "network change, use_mobile_network=" + AppModel.sDevMobileWork);
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
        sPreferences.edit().putInt(PER_VERSION, sVersionCode).apply();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            sLang = sActivity.getResources().getConfiguration().getLocales().toString();
        }else {
            sLang = sActivity.getResources().getConfiguration().locale.toString();
        }
        Intent intent = new Intent(activity,XXnetService.class);
        activity.startService(intent);
    }
}
