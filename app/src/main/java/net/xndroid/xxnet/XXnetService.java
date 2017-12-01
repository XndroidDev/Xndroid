package net.xndroid.xxnet;

import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.os.IBinder;
import android.support.v4.app.NotificationCompat;

import net.xndroid.AppModel;
import net.xndroid.MainActivity;
import net.xndroid.R;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import java.io.File;
import java.io.OutputStreamWriter;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;
import java.util.ListIterator;

import static net.xndroid.AppModel.sActivity;
import static net.xndroid.AppModel.sDevMobileWork;
import static net.xndroid.AppModel.sXndroidFile;

public class XXnetService extends Service {

    private final int NOTIFICATION_ID = 0x4321;
    private Process mProcess;

    private static XXnetService sDefaultService;
    public static XXnetService getDefaultService(){
        return sDefaultService;
    }


    public XXnetService() {
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
        LogUtils.i("rm path=" + path +",postfixs=" +
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
                            LogUtils.i("delete file:" + file.getAbsolutePath());
                        }
                        else{
                            String[] parts = file.getName().split("\\.");
                            if(parts.length >= 2)
                                for(String postfix: postfixs)
                                    if(postfix.equals(parts[parts.length-1]))
                                    {
                                        file.delete();
                                        LogUtils.i("delete file:" + file.getAbsolutePath());
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
                LogUtils.i("remove directory: " + file.getAbsolutePath());
            }
        }
    }


    private void removeUselessFiles()
    {
        if(XXnetManager.sIpNum >=0 && XXnetManager.sXXversion.indexOf(".") > 0){
            String version = XXnetManager.sXXversion;
            String codePath = sXndroidFile + "/xxnet/code";
            LogUtils.i("XX-Net version is " + version + ", remove useless files");
            for(File file : new File(codePath).listFiles()){
                String fileName = file.getName();
                if(!fileName.equals(version) && !fileName.equals("version.txt")){
                    ShellUtils.execBusybox("rm -rf " + codePath + "/" +fileName);
                }
            }
            ShellUtils.execBusybox("ln -sf " + codePath + "/" + version + " " + codePath + "/default");
			ShellUtils.execBusybox("rm -r " + sXndroidFile + "/xxnet/data/downloads");
            ShellUtils.execBusybox("rm -r " + sXndroidFile + "/xxnet/SwitchyOmega");

            String[] deletePaths = {
                    "/python27/1.0/WinSxS",
                    "/python27/1.0/lib/win32",
                    "/python27/1.0/lib/linux",
            };

            for(String deletepath : deletePaths){
                rm(codePath + "/" + version + deletepath, null);
            }

            rm(codePath + "/" + version + "/python27",new String[] {"exe", "dll"});
            ShellUtils.execBusybox("chmod -R 777 " + sXndroidFile + "/xxnet");
        }

    }


    private final int IP_QUALITY_LIMIT = 500;
    private final int IP_NUM_LIMIT = 60;
    public static int MAX_THREAD_NUM = 12;

    private int giveThreadNum(){
        if(XXnetManager.sIpQuality < 0 || XXnetManager.sIpNum < 0 ||
                (XXnetManager.sWorkerH1 == 0 && XXnetManager.sWorkerH2 == 0))
            return MAX_THREAD_NUM;
        boolean goodQuality = XXnetManager.sIpQuality < IP_QUALITY_LIMIT;
        boolean goodNum = XXnetManager.sIpNum > IP_NUM_LIMIT;
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
            XXnetManager.setThreadNum(giveThreadNum());
        }
        if(!AppModel.sDevScreenOff) {
            XXnetManager.updateState();
            if (AppModel.sUpdateInfoUI != null && sActivity != null)
                sActivity.runOnUiThread(AppModel.sUpdateInfoUI);
            String mesg = getString(R.string.ip_number) + ":" + XXnetManager.sIpNum
                    + "            " + getString(R.string.ip_quality) + ":" + XXnetManager.sIpQuality;
            notification(XXnetManager.sStateSummary,mesg);
        }

    }


    private boolean mExitFlag = false;
    private void watchXXnet()
    {
        new Thread(new Runnable() {
            @Override
            public void run() {
                while(true)
                {
                    try {
                        if(mExitFlag)
                            return;
                        doWatch();
                        if(AppModel.sDevScreenOff || !AppModel.sIsForeground)
                            Thread.sleep(6000);
                        else
                            Thread.sleep(3000);

                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            }
        }).start();
    }



    private void startXXnet()
    {
        new Thread(new Runnable() {
            @Override
            public void run() {
                String cmd = "export LANG=" + AppModel.sLang + " \n"
                        + ((AppModel.sDebug || AppModel.sLastFail)?"export DEBUG=TRUE\n":"")
                        + "cd " + sXndroidFile + " \n"
                        + sXndroidFile + "/python/bin"
                        + (Build.VERSION.SDK_INT >=19?"/python-launcher.sh ":"python-launcher-nopie.sh ")
                        + sXndroidFile + "/xxnet/android_start.py > " + sXndroidFile + "/log/xxnet-output.log 2>&1 \nexit\n";
                LogUtils.i("try to start xxnet, cmd: " + cmd);
                try {
                    mProcess = Runtime.getRuntime().exec(sXndroidFile + "/busybox sh");
                    OutputStreamWriter sInStream = new OutputStreamWriter(mProcess.getOutputStream());
                    sInStream.write(cmd);
                    sInStream.flush();
                    mProcess.waitFor();
                } catch (Exception e) {
                    AppModel.fatalError("XX-Net process fail:" + e.getMessage());
                }
                mProcess = null;
                LogUtils.i("XX-Net exit.");
                if(!AppModel.sAppStoped)
                    AppModel.fatalError(getString(R.string.xxnet_exit_un));
            }
        }).start();

    }


    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        sDefaultService = this;
        startXXnet();
        watchXXnet();
        return super.onStartCommand(intent, flags, startId);
    }


    //don't call it in main thread!
    public void postStop()
    {
        if(mExitFlag)
            return;
        mExitFlag = true;
        if(mProcess != null)
            if(!XXnetManager.quit()){
                if(mProcess != null) {
                    mProcess.destroy();
                }
                mProcess = null;
            }
        stopForeground(true);
        this.stopSelf();
        removeUselessFiles();
    }


    public boolean exitFinished(){
        return mProcess == null;
    }


    @Override
    public void onDestroy() {
        postStop();
        super.onDestroy();
    }


    @Override
    public IBinder onBind(Intent intent) {
        // TODO: Return the communication channel to the service.
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
