package net.xndroid;


import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;

import net.xndroid.utils.HttpJson;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import java.io.File;

import static net.xndroid.AppModel.sContext;

class DownloadReceiver extends BroadcastReceiver{

    @Override
    public void onReceive(Context context, Intent intent) {
        if(intent.getAction().equals(DownloadManager.ACTION_DOWNLOAD_COMPLETE)){
            if(intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1)==UpdateManager.sDownloadId)
            {
                if(UpdateManager.sDownloadPath!=null && UpdateManager.sDownloadPath.length() > 0){
                    LogUtils.i("download apk finished, start to install");
                    Intent callIntent = new Intent(Intent.ACTION_VIEW);
                    callIntent.setDataAndType(Uri.parse("file://"+ UpdateManager.sDownloadPath), "application/vnd.android.package-archive");
                    callIntent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK );
                    context.startActivity(callIntent);
                    if(sContext != null) {
                        String oldApkPath = context.getApplicationContext().getPackageResourcePath();
                        ShellUtils.execBusybox("cp -f " + oldApkPath + " " + "/sdcard/xndroid-old.apk");
                        AppModel.showToast(sContext.getString(R.string.install_new_tip));
                    }
                }
            }
        }
    }
}


public class UpdateManager {

    public static final String PER_IGNORE_VERSION = "XNDROID_IGNORE_VERSION";
    public static final String PER_UPDATE_POLICY = "XNDROID_UPDATE_POLICY";
    public static final int UPDATE_ALL = 2;
    public static final int UPDATE_STABLE = 1;
    public static final int UPDATE_OFF = 0;

    public static String sDownloadPath = "";
    public static long sDownloadId = 0;
    private static boolean sStableVersion = true;
    private static String sVersionName = "";

    private static final String sUpdateUrl =  "https://raw.githubusercontent.com/XndroidDev/Xndroid-update/master/update";

    public static void setUpdatePolicy(Context context){
        new AlertDialog.Builder(context).setTitle(R.string.update_policy)
                .setMessage(R.string.update_policy_tip)
                .setPositiveButton(R.string.notice_latest, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        AppModel.sPreferences.edit().putInt(PER_UPDATE_POLICY, UPDATE_ALL).apply();
                    }
                }).setNeutralButton(R.string.notice_stable, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        AppModel.sPreferences.edit().putInt(PER_UPDATE_POLICY, UPDATE_STABLE).apply();
                    }
                }).setNegativeButton(R.string.no_update, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        AppModel.sPreferences.edit().putInt(PER_UPDATE_POLICY, UPDATE_OFF).apply();
                    }
                }).create().show();
    }

    private static String getUpdateLog(int version){
        boolean chinese = AppModel.sLang.startsWith("zh");
        String log = "";
        int curVersion = AppModel.sVersionCode;
        if(AppModel.sDebug){
            curVersion--;
        }
        while (curVersion++ < version){
            log += HttpJson.get(sUpdateUrl + "/update_log_" +
                    (chinese ? "zh" : "en") + "_" + curVersion);
            log += "\n";
        }
        return log;
    }

    private static void doUpdate()
    {
        sContext.registerReceiver(new DownloadReceiver(),
                new IntentFilter("android.intent.action.DOWNLOAD_COMPLETE" ));
        String url = "https://raw.githubusercontent.com/XndroidDev/Xndroid-update/master/update/app-debug.apk";
        if(sStableVersion){
            url = "https://github.com/XndroidDev/Xndroid/releases/download/" + sVersionName + "/app-release.apk";
        }
        DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
        request.setAllowedNetworkTypes(DownloadManager.Request.NETWORK_WIFI);
        request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);
        request.setTitle(sContext.getString(R.string.updating_xndroid));
        request.setDescription(sContext.getString(R.string.downloading_xndroid));
        String dir = "update";
        String apk = "Xndroid.apk";
        request.setDestinationInExternalFilesDir(sContext, dir ,apk);
        sDownloadPath = sContext.getExternalFilesDir(null)+"/"+ dir+"/"+apk;
        File file = new File(sDownloadPath);
        if(file.isFile())
            file.delete();
        DownloadManager downManager = (DownloadManager) sContext.getSystemService(Context.DOWNLOAD_SERVICE);
        sDownloadId = downManager.enqueue(request);
    }


    private static void showUpdate(final int version){
        //this code don't run in main thread
        String versionName = "";
        String versionLog = "";
        if(sStableVersion){
            versionName = HttpJson.get(sUpdateUrl + "/latest_version_name");
        }else {
            versionName = HttpJson.get(sUpdateUrl + "/latest_debug_name");
        }
        if(versionName.isEmpty()){
            LogUtils.e("fail to get version name");
            AppModel.showToast(sContext.getString(R.string.get_version_fail));
            return;
        }
        versionLog = getUpdateLog(version);
        sVersionName = versionName;

        final String finalVersionLog = versionLog;
        final String finalVersionName = versionName;

        //this code run in main thread.
        AppModel.sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                AlertDialog.Builder builder = new AlertDialog.Builder(AppModel.sActivity);
                if(version > AppModel.sVersionCode || (AppModel.sDebug && sStableVersion && version == AppModel.sVersionCode)){
                    builder.setTitle(sContext.getString(R.string.find_new_version) + finalVersionName
                            + (sStableVersion?sContext.getString(R.string.stable_b): sContext.getString(R.string.test_b)));
                    builder.setMessage(finalVersionLog);
                    builder.setPositiveButton(R.string.update, new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            AppModel.showToast(sContext.getString(R.string.update_xndroid_to) + finalVersionName);
                            LogUtils.i("update Xndroid to " + version);
                            doUpdate();
                        }
                    });
                    builder.setNeutralButton(R.string.ignore, new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            AppModel.showToast(sContext.getString(R.string.ignore_version) + finalVersionName);
                            LogUtils.i("ignore version " + version);
                            AppModel.sPreferences.edit().putInt(PER_IGNORE_VERSION, version).commit();
                        }
                    });
                }else {
                    builder.setTitle(R.string.no_new_version);
                    if(version == 0)
                        builder.setMessage(R.string.get_version_fail);
                    else
                        builder.setMessage(R.string.current_latest);
                    builder.setPositiveButton(R.string.ok, null);
                }
                builder.create().show();
            }
        });

    }

    /**
     *Don not call it in main thread!
     * */
    public static void checkUpdate(boolean checkall){
        try {
            int version = getXndroidLatestVersion();
            if (!checkall) {
                if(version < AppModel.sVersionCode)
                    return;
                if(version == AppModel.sVersionCode && !(AppModel.sDebug && sStableVersion))
                    return;
                if(AppModel.sPreferences.getInt(PER_UPDATE_POLICY, UPDATE_ALL) == UPDATE_OFF)
                    return;
                int ignoreVersion = AppModel.sPreferences.getInt(PER_IGNORE_VERSION, 0);
                if (ignoreVersion == version)
                    return;
            }
            if(AppModel.sIsForeground) {
                showUpdate(version);
            }else {
                AppModel.showToast(sContext.getString(R.string.find_new_version) + version + sContext.getString(R.string.update_tip));
            }
        }catch (Exception e){
            AppModel.showToast("checkUpdate error");
            LogUtils.e("checkUpdate error ", e);
        }
    }


    private static int getXndroidLatestVersion(){
        int version = 0;
        int versionDebug = 0;
        String versionDebugStr = "";
        String versionStr = HttpJson.get(sUpdateUrl + "/latest_version_code");
        if(versionStr.length() == 0){
            versionStr = HttpJson.get(sUpdateUrl + "/latest_version_code");
        }
        if(AppModel.sPreferences.getInt(PER_UPDATE_POLICY, UPDATE_ALL) == UPDATE_ALL){
            versionDebugStr = HttpJson.get(sUpdateUrl + "/latest_debug_code");
            if(versionDebugStr.length() == 0){
                versionDebugStr = HttpJson.get(sUpdateUrl + "/latest_debug_code");
            }
        }
        try {
            if(versionStr.length() > 0)
                version = Integer.parseInt(versionStr);
            if(versionDebugStr.length() > 0)
                versionDebug = Integer.parseInt(versionDebugStr);
        }catch (Exception e){
            e.printStackTrace();
        }
        sStableVersion = (version >= versionDebug);
        return (version >= versionDebug ? version : versionDebug);
    }
}

//    private static boolean isNew(String ver1, String ver2){
//        String[] ver1s = ver1.split("\\.");
//        String[] ver2s = ver2.split("\\.");
//        if(ver1s.length != 3 || ver2s.length != 3)
//            return false;
//        try {
//            int v1 = Integer.parseInt(ver1s[0]);
//            int v2 = Integer.parseInt(ver2s[0]);
//            if(v1 > v2)
//                return true;
//            else if(v1 == v2){
//                v1 = Integer.parseInt(ver1s[1]);
//                v2 = Integer.parseInt(ver2s[1]);
//                if(v1 > v2)
//                    return true;
//                else if(v1 ==v2){
//                    v1 = Integer.parseInt(ver1s[2]);
//                    v2 = Integer.parseInt(ver2s[2]);
//                    if(v1 > v2)
//                        return true;
//                }
//            }
//
//        }catch (Exception e){
//            e.printStackTrace();
//        }
//        return false;
//
//    }



//    private static void showUpdate(final int version){
//        //this don't run in main thread.
//        String versionName = "0.0.0";
//        if(version > AppModel.sVersionCode)
//            HttpJson.get(sUpdateUrl + "/latest_version_name");
////        JSONObject updateVersions = null;
////        if(showXXnet)
////            updateVersions = HttpJson.getJson("http://127.0.0.1:8085/update?cmd=get_new_version");
//
//
//
//        //this run in main thread
//        View view = AppModel.sActivity.getLayoutInflater().inflate(R.layout.update_layout, null, false);
//        TextView xndroidTitle = view.findViewById(R.id.xndroid_update_title);
//        TextView xndroidLog = view.findViewById(R.id.xndroid_update_log);
//        View xndroidUpdate = view.findViewById(R.id.xndroid_update_update);
//        View xndroidIgnore = view.findViewById(R.id.xndroid_update_ignore);
//        if(version > AppModel.sVersionCode){
//            xndroidTitle.setText("new version:" + versionName);
//            xndroidLog.setText(getUpdateLog(version));
//            xndroidUpdate.setOnClickListener(new View.OnClickListener() {
//                @Override
//                public void onClick(View v) {
//                    doUpdate();
//                }
//            });
//            xndroidIgnore.setOnClickListener(new View.OnClickListener() {
//                @Override
//                public void onClick(View v) {
//                    doIgnore(version);
//                }
//            });
//        }else {
//            xndroidTitle.setText("No new version");
//            if(version == 0)
//                xndroidLog.setText("Get latest Xndroid version fail!");
//            else
//                xndroidLog.setText("Current Xndroid is latest.");
//            xndroidIgnore.setVisibility(View.INVISIBLE);
//            xndroidUpdate.setVisibility(View.INVISIBLE);
//        }
//
//
////        if(showXXnet) {
////            if(updateVersions == null){
////
////            }else {
////                String xxnetVersion = "0.0.0";
////                String xxnetStable = "0.0.0";
////                String xxnetTest = "0.0.0";
////                try {
////                    xxnetVersion = updateVersions.getString("current_version");
////                    xxnetStable = updateVersions.getString("stable_version");
////                    xxnetTest = updateVersions.getString("test_version");
////                } catch (Exception e) {
////                    e.printStackTrace();
////                }
////                TextView xxnetVersionView = view.findViewById(R.id.xndroid_update_xxnet_cur_title);
////                xxnetVersionView.setText(xxnetVersion);
////                TextView xxnetStableView = view.findViewById(R.id.xndroid_update_xxnet_stable_title);
////                xxnetStableView.setText(xxnetStable);
////                if(isNew(xxnetStable, xxnetVersion)){
////
////                }
////            }
////
////        }
//
//
//    }
