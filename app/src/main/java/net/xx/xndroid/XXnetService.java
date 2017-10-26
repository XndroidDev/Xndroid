package net.xx.xndroid;

import android.annotation.TargetApi;
import android.app.Activity;
import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.BitmapFactory;
import android.net.ConnectivityManager;
import android.os.Build;
import android.os.IBinder;
import android.support.v4.app.NotificationCompat;
import android.util.Log;

import net.xx.xndroid.util.LogUtil;
import net.xx.xndroid.util.ShellUtil;
import net.xx.xndroid.xxnet.XXnetAttribute;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;
import java.util.ListIterator;

import static android.os.Build.VERSION_CODES.M;
import static net.xx.xndroid.AppModel.appStop;
import static net.xx.xndroid.AppModel.checkNetwork;
import static net.xx.xndroid.AppModel.sActivity;
import static net.xx.xndroid.AppModel.sDevMobileWork;
import static net.xx.xndroid.AppModel.sXndroidFile;
import static net.xx.xndroid.AppModel.showToast;

public class XXnetService extends Service {

    private final int NOTIFICATION_ID = 0x4321;
    private Process mProcess;

    private static XXnetService sDefaultService;
    public static XXnetService getDefaultService(){
        return sDefaultService;
    }


    public XXnetService() {
    }

    private static final String[] sPermissions = {
            "android.permission.INTERNET",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.ACCESS_NETWORK_STATE"};


    @TargetApi(M)
    static private void getPermission(String[] permissions,Activity activity)
    {
        if(Build.VERSION.SDK_INT>=23) {
            ArrayList<String> preToDo = new ArrayList<>();
            boolean tip = false;
            for (String pre : permissions) {
                if (activity.checkSelfPermission(pre) != PackageManager.PERMISSION_GRANTED) {
                    preToDo.add(pre);
                    if (activity.shouldShowRequestPermissionRationale(pre)) {
                        tip = true;
                    }
                }
            }
            if (preToDo.size() == 0)
                return;
            if (tip)
                showToast(sActivity.getString(R.string.permissions_need));
            activity.requestPermissions(preToDo.toArray(new String[preToDo.size()]), 0);
        }
    }


    private static void writeRawFile(int id, String destPath)
    {
        InputStream input = sActivity.getResources().openRawResource(id);
        byte[] buff = new byte[512*1024];
        try {
            FileOutputStream output = new FileOutputStream(destPath);
            int count;
            while ((count=input.read(buff))>0)
                output.write(buff,0,count);
            output.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }


    private static void fileShellInit()
    {
        String busybox = sXndroidFile + "/busybox";
        String gzFile = sXndroidFile + "/gzfile";
        if(new File(busybox).exists() == false)
        {
            File xndroidFile = new File(sXndroidFile);
            if(!xndroidFile.isDirectory())
                xndroidFile.mkdirs();
            writeRawFile(R.raw.busybox,busybox);
            writeRawFile(R.raw.xndroid_files,gzFile);
            if(!new File(busybox).setExecutable(true, false)){
                Log.d("xndroid_debug", "Error:setExecutable fail!");
            }
            ShellUtil.init(sXndroidFile);
            ShellUtil.execBusybox("tar -C "+ sXndroidFile +" -xvf "+gzFile);
            if(ShellUtil.stdErr !=null || new File(sXndroidFile+"/xxnet/android_start.py").exists() == false)
                throw new RuntimeException("unzip file fail!");
            new File(gzFile).delete();
        }else {
            ShellUtil.init(sXndroidFile);
        }
    }



    private void notification(String title,String mesg){
        NotificationCompat.Builder builder=new NotificationCompat.Builder(this);
        builder.setSmallIcon(R.mipmap.ic_launcher);
        builder.setLargeIcon(BitmapFactory.decodeResource(getResources(),R.mipmap.ic_launcher));
        builder.setAutoCancel(false);
        //禁止滑动删除
        builder.setOngoing(true);
        builder.setShowWhen(false);
        builder.setContentTitle(title);
        builder.setContentText(mesg);
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(this,0,intent,PendingIntent.FLAG_UPDATE_CURRENT);
        builder.setContentIntent(pendingIntent);
        Notification notification = builder.build();
        startForeground(NOTIFICATION_ID,notification);
    }


    public static void rm(String path, String[] postfixs){
        LogUtil.defaultLogWrite("info", "rm path=" + path +",postfixs=" +
                (postfixs == null ? "null" : postfixs.toString()));
        File topFile = new File(path);
        if(!topFile.exists())
            return;
        if(!topFile.isDirectory())
            topFile.delete();
        List<File> toHandle = new LinkedList<>();
        List<File> toDelete = new ArrayList<>();
        toHandle.add(topFile);
        while (toHandle.size() > 0){
            ListIterator<File> iterator = toHandle.listIterator();
            while(iterator.hasNext()){
                File parDir = iterator.next();
                iterator.remove();
                toDelete.add(parDir);
                for(File file : parDir.listFiles()){
                    if(file.isDirectory())
                        iterator.add(file);
                    else {
                        if(postfixs == null) {
                            file.delete();
                            LogUtil.defaultLogWrite("info", "delete file:" + file.getAbsolutePath());
                        }
                        else{
                            String[] parts = file.getName().split("\\.");
                            if(parts.length >= 2)
                                for(String postfix: postfixs)
                                    if(postfix.equals(parts[parts.length-1]))
                                    {
                                        file.delete();
                                        LogUtil.defaultLogWrite("info", "delete file:" + file.getAbsolutePath());
                                        break;
                                    }
                        }
                    }
                }

            }
        }
        ListIterator<File> iterator = toDelete.listIterator(toDelete.size() - 1);
        while(iterator.hasPrevious())
        {
            File file = iterator.previous();
            if(file.listFiles().length == 0) {
                file.delete();
                LogUtil.defaultLogWrite("info", "remove directory: " + file.getAbsolutePath());
            }
        }
    }


    private void removeUselessFiles()
    {

        if(XXnetAttribute.sIpNum >=0 && XXnetAttribute.sXXversion.indexOf(".") > 0){
            String version = XXnetAttribute.sXXversion;
            String codePath = sXndroidFile + "/xxnet/code";
            LogUtil.defaultLogWrite("info", "XX-net version is " + version + ", remove useless files");
            for(File file : new File(codePath).listFiles()){
                String fileName = file.getName();
                if(!fileName.equals(version) && !fileName.equals("version.txt")){
                    ShellUtil.execBusybox("rm -rf " + codePath + "/" +fileName);
                }
            }
            ShellUtil.execBusybox("ln -sf " + codePath + "/" + version + " " + codePath + "/default");
			ShellUtil.execBusybox("rm -r " + sXndroidFile + "/xxnet/data/downloads");
            ShellUtil.execBusybox("rm -r " + sXndroidFile + "/xxnet/SwitchyOmega");

            String[] deletePaths = {
                    "/python27/1.0/WinSxS",
                    "/python27/1.0/lib/win32",
                    "/python27/1.0/lib/linux",
            };

            for(String deletepath : deletePaths){
                rm(codePath + "/" + version + deletepath, null);
            }

            rm(codePath + "/" + version + "/python27",new String[] {"exe", "dll"});
            ShellUtil.execBusybox("chmod -R 777 " + sXndroidFile + "/xxnet");
        }

    }


    private final int IP_QUALITY_LIMIT = 500;
    private final int IP_NUM_LIMIT = 40;
    public static int MAX_THREAD_NUM = 16;

    private int giveThreadNum(){
        if(XXnetAttribute.sIpQuality < 0 || XXnetAttribute.sIpNum < 0 ||
                (XXnetAttribute.sWorkerH1 == 0 && XXnetAttribute.sWorkerH2 == 0))
            return MAX_THREAD_NUM;
        boolean goodQuality = XXnetAttribute.sIpQuality < IP_QUALITY_LIMIT;
        boolean goodNum = XXnetAttribute.sIpNum > IP_NUM_LIMIT;
        if(AppModel.sDevScreenOff){
            if(AppModel.sDevBatteryLow)
                return 0;
            if(!goodQuality)
                if(sDevMobileWork)
                    return MAX_THREAD_NUM /2;
                else
                    return MAX_THREAD_NUM;
            else if(!goodNum)
                return MAX_THREAD_NUM /2;
            else
                return 0;
        }else {
            if(goodQuality && goodNum){
                if(AppModel.sDevBatteryLow || sDevMobileWork)
                    return 0;
                else
                    return MAX_THREAD_NUM /2;
            }else {
                if(AppModel.sDevBatteryLow)
                    return MAX_THREAD_NUM /2;
                else if(sDevMobileWork && goodQuality)
                    return MAX_THREAD_NUM /2;
                else
                    return MAX_THREAD_NUM;
            }
        }

    }


    private void doWatch(){
        if(AppModel.sAutoThread) {
            XXnetAttribute.setThreadNum(giveThreadNum());
        }
        if(!AppModel.sDevScreenOff) {
            XXnetAttribute.updateState();
            if (AppModel.sUpdateInfoUI != null)
                sActivity.runOnUiThread(AppModel.sUpdateInfoUI);
        }
        //即使休眠也仍然发送通知,避免被系统强行终止
        String mesg = getString(R.string.ip_number) + ":" + XXnetAttribute.sIpNum
                + "            " + getString(R.string.ip_quality) + ":" + XXnetAttribute.sIpQuality;
        notification(XXnetAttribute.sStateSummary,mesg);
    }


    private boolean mExitFlag = false;
    private void watchXXnet()
    {
        new Thread(new Runnable() {
            @Override
            public void run() {
                while(true)
                {
                    if(mExitFlag)
                        return;
                    doWatch();
                    try {
                        if(AppModel.sDevScreenOff || !AppModel.sIsForeground)
                            Thread.sleep(5000);
                        else
                            Thread.sleep(2000);

                    } catch (InterruptedException e) {
                        e.printStackTrace();
                    }
                }
            }
        }).start();

    }


    //the receiver should be registered in service not in activity.
    private BroadcastReceiver mReceiver;

    private void regReceiver(){
        mReceiver = new XndroidReceiver();
        IntentFilter intentFilter = new IntentFilter();
        intentFilter.addAction(Intent.ACTION_BATTERY_CHANGED);
        intentFilter.addAction(ConnectivityManager.CONNECTIVITY_ACTION);
        intentFilter.addAction(Intent.ACTION_SCREEN_ON);
        intentFilter.addAction(Intent.ACTION_SCREEN_OFF);
        this.registerReceiver(mReceiver, intentFilter);
    }


    private void startXXnet()
    {
        new Thread(new Runnable() {
            @Override
            public void run() {
                String cmd = sXndroidFile + "/busybox sh " + sXndroidFile
                        + "/start.sh " + AppModel.sLang;
                LogUtil.defaultLogWrite("info","try to start xxnet, cmd=" + cmd);
                try {
                    mProcess = Runtime.getRuntime().exec(cmd);
                    mProcess.waitFor();
                } catch (Exception e) {
                    e.printStackTrace();
                    LogUtil.defaultLogWrite("error","xxnet run fail:" + e.getMessage());
                }
                mProcess = null;
                LogUtil.defaultLogWrite("info", "XX-Net exit.");
                postStop();
            }
        }).start();

    }


    private static void checkXndroidUpdate(){
        if(!sDevMobileWork){
            new Thread(new Runnable() {
                @Override
                public void run() {
                    UpdateManager.checkUpdate(false);
                }
            }).start();
        }
    }


    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        sDefaultService = this;
        new WorkingDlg(AppModel.sActivity, sActivity.getString(R.string.xndroid_launching)) {
            @Override
            void work() {
                updataMesg(sActivity.getString(R.string.initializing));
                LogUtil.sSetDefaultLog(new LogUtil(sXndroidFile+"/xndroid.log"));
                checkNetwork();
                checkXndroidUpdate();
                updataMesg(sActivity.getString(R.string.request_permission));
                getPermission(sPermissions,sActivity);
                updataMesg(sActivity.getString(R.string.unzip_file));
                fileShellInit();
                updataMesg(sActivity.getString(R.string.start_xxnet));
                startXXnet();
                watchXXnet();
            }
        };
        regReceiver();
        return super.onStartCommand(intent, flags, startId);
    }


    //don't call it in main thread!
    public void postStop()
    {
        if(mExitFlag)
            return;
        mExitFlag = true;
        if(mProcess != null)
        {
            if(XXnetAttribute.quit())
            {
                try
                {
                    for(int i=0;i<30;i++) {
                        if(mProcess == null)
                            break;
                        Thread.sleep(100);
                    }
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
            if(mProcess != null)
                mProcess.destroy();
            mProcess = null;
        }
        stopForeground(true);
        this.stopSelf();
        sDefaultService = null;
        removeUselessFiles();
        LogUtil.defaultLogWrite("info", "appStop");
        ShellUtil.close();
        LogUtil.sGetDefaultLog().close();
        appStop();
    }


    @Override
    public void onDestroy() {
        this.unregisterReceiver(mReceiver);
        postStop();
        super.onDestroy();
    }


    @Override
    public IBinder onBind(Intent intent) {
        // TODO: Return the communication channel to the service.
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
