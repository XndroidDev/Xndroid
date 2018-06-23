package net.xndroid.xxnet;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.os.IBinder;
import android.support.v4.app.NotificationCompat;
import android.util.Log;

import net.xndroid.AppModel;
import net.xndroid.MainActivity;
import net.xndroid.R;
import net.xndroid.utils.FileUtils;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;

import java.io.OutputStreamWriter;

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

    private final String CHANNEL_ID = "channel_xxnet_state";

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
        //builder.setChannel(CHANNEL_ID);
        Notification notification = builder.build();
        startForeground(NOTIFICATION_ID, notification);
    }


    private void removeUselessFiles() {
        if(XXnetManager.sIpNum > 0 && XXnetManager.sXXversion.indexOf(".") > 0){
            String version = ShellUtils.execBusybox("cat " + AppModel.sXndroidFile + "/xxnet/code/version.txt").trim();
            String codePath = sXndroidFile + "/xxnet/code";
            LogUtils.i("XX-Net version is " + version + ", remove useless files");
            FileUtils.rmExclude(codePath, new String[]{"version.txt", version});
            String pwd = ShellUtils.execBusybox("pwd").trim();
            ShellUtils.exec("cd " + codePath);
            ShellUtils.execBusybox("ln -s " + version + " default");
            ShellUtils.exec("cd " + pwd);
            ShellUtils.execBusybox("rm -r " + sXndroidFile + "/xxnet/data/downloads");
            ShellUtils.execBusybox("rm -r " + sXndroidFile + "/xxnet/SwitchyOmega");
            ShellUtils.execBusybox("rm -r " + codePath + "/" + version + "/gae_proxy/server");
            ShellUtils.execBusybox("rm -r " + codePath + "/" + version + "/python27/1.0/WinSxS");
            FileUtils.rmExclude(codePath + "/" + version + "/python27/1.0/lib", new String[] {"noarch"});
            ShellUtils.execBusybox("rm -r " + codePath + "/" + version + "/python27/1.0/*.exe");
            ShellUtils.execBusybox("rm -r " + codePath + "/" + version + "/python27/1.0/*.dll");
        }

    }


    private final int IP_QUALITY_LIMIT = 700;
    private final int IP_NUM_LIMIT = 200;
    public static int MAX_THREAD_NUM = 12;

    private int giveThreadNum(){
        if(XXnetManager.sIpQuality <= 0 || XXnetManager.sIpQuality >= 3000 || XXnetManager.sIpNum <= 0 ||
                (XXnetManager.sWorkerH1 == 0 && XXnetManager.sWorkerH2 == 0 && !XXnetManager.sIsIdle))
            return MAX_THREAD_NUM;
        boolean goodQuality = XXnetManager.sIpQuality < IP_QUALITY_LIMIT;
        boolean goodNum = XXnetManager.sIpNum > IP_NUM_LIMIT;
        if(AppModel.sDevScreenOff){
            if(AppModel.sDevBatteryLow)
                return 0;
            if(goodQuality)
                return 0;
            if(sDevMobileWork)
                return 0;
            return MAX_THREAD_NUM/2;
        }else {
            if(goodQuality && goodNum){
                if(AppModel.sDevBatteryLow || sDevMobileWork)
                    return 0;
                else
                    return MAX_THREAD_NUM /3;
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
            if(AppModel.sEnableNotification)
                notification(XXnetManager.sStateSummary, mesg);
        }

    }


    private boolean mExitFlag = false;
    private void watchXXnet() {
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
                            Thread.sleep(5000);
                        else
                            Thread.sleep(3000);

                    } catch (Exception e) {
                        LogUtils.e("watch XX-Net fail ", e);
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
                byte[] output = new byte[1024];
                int readLen = 0;
                byte[] error = new byte[1024];
                int errorLen = 0;
                String cmd = "cd " + sXndroidFile + " \n"
                        + "export LANG=" + AppModel.sLang + " \n"
                        + "export PATH=" + sXndroidFile + ":$PATH\n"
//                        + "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/vendor/lib64:/vendor/lib:/system/lib64:/system/lib\n"
                        + ((AppModel.sDebug || AppModel.sLastFail)?"export DEBUG=TRUE\n":"")
                        + "sh " + sXndroidFile + "/python/bin"
                        + (Build.VERSION.SDK_INT >17?"/python-launcher.sh ":"/python-launcher-nopie.sh ")
                        + sXndroidFile + "/xxnet/android_start.py protect_sock "
                        + (AppModel.sIsRootMode?"root_mode":"vpn_mode")
                        + " > " + sXndroidFile + "/log/xxnet-output.log 2>&1 \nexit\n";
                LogUtils.i("try to start xxnet, cmd: " + cmd);
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
                    LogUtils.e("XX-Net process fail ", e);
                }
                mProcess = null;
                LogUtils.i("xxnet exit output :\n" + (readLen <= 0 ? "" : new String(output, 0, readLen)));
                LogUtils.i("xxnet exit error :\n" + (errorLen <= 0 ? "" : new String(error, 0, errorLen)));
                if(!AppModel.sAppStoped)
                    AppModel.fatalError(getString(R.string.xxnet_exit_un));
            }
        }).start();

    }


    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        sDefaultService = this;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationManager mNotificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
                NotificationChannel channel = new NotificationChannel(CHANNEL_ID, "Channel XX-Net state", NotificationManager.IMPORTANCE_DEFAULT);
                channel.setDescription("Show the state of XX-Net");
                channel.enableLights(false);
                channel.enableVibration(false);
                mNotificationManager.createNotificationChannel(channel);
            }
            startXXnet();
            watchXXnet();
        }catch (Exception e){
            LogUtils.e("start XX-Net fail ", e);
            AppModel.fatalError("unexpected exception: " + e.getMessage());
        }
        return START_NOT_STICKY;
    }


    //don't call it in main thread
    public void postStop() {
        if(mExitFlag)
            return;
        mExitFlag = true;
        stopXXnet();
        removeUselessFiles();
    }

    public void stopXXnet(){
        if(mProcess != null) {
            if (!XXnetManager.quit()) {
                Log.e("xndroid_log", "xxnet quit fail");
                if (mProcess != null) {
                    Log.w("xndroid_log", "destroy xxnet");
                    mProcess.destroy();
                }
                mProcess = null;
            }
        }
        stopForeground(true);
        this.stopSelf();
    }



    public boolean exitFinished(){
        return mProcess == null;
    }


    @Override
    public void onDestroy() {
//        postStop();
        super.onDestroy();
    }


    @Override
    public IBinder onBind(Intent intent) {
        // TODO: Return the communication channel to the service.
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
