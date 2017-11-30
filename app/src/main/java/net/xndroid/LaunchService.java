package net.xndroid;

import android.annotation.TargetApi;
import android.app.Activity;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.os.Build;
import android.os.IBinder;

import net.xndroid.fqrouter.FqrouterManager;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;
import net.xndroid.xxnet.XXnetManager;
import net.xndroid.xxnet.XXnetService;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;

import static android.os.Build.VERSION_CODES.M;
import static net.xndroid.AppModel.checkNetwork;
import static net.xndroid.AppModel.sActivity;
import static net.xndroid.AppModel.sAutoThread;
import static net.xndroid.AppModel.sDebug;
import static net.xndroid.AppModel.sDevMobileWork;
import static net.xndroid.AppModel.sLang;
import static net.xndroid.AppModel.sLastFail;
import static net.xndroid.AppModel.sLastVersion;
import static net.xndroid.AppModel.sVersionCode;
import static net.xndroid.AppModel.sVersionName;
import static net.xndroid.AppModel.sXndroidFile;
import static net.xndroid.AppModel.showToast;

public class LaunchService extends Service {
    public LaunchService() {
    }

    private static LaunchService sDefaultService;

    public static LaunchService getDefaultService(){
        return sDefaultService;
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



    private static boolean writeRawFile(int id, String destPath)
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
            return false;
        }
        return true;
    }

    public static boolean prepareRawFile(int fileId, String path){
        if(new File(path).exists())
            return true;
        File dir = new File(path).getParentFile();
        if(!dir.isDirectory())
            if(!dir.mkdirs())
                return false;
        return writeRawFile(fileId, path);
    }

    public static boolean unzipRawFile(int fileId, String dirPath){
        String filePath = sXndroidFile + "/tmp-" + fileId + ".tar.gz";
        if(!prepareRawFile(fileId, filePath))
            return false;
        ShellUtils.execBusybox("tar -C " + dirPath + " -xvf " + filePath);
        ShellUtils.execBusybox("chmod -R 777 " + dirPath);
        new File(filePath).delete();
        return true;
    }

    private static void pythonInit(){
        if(new File(sXndroidFile + "/python/bin/python").exists())
            return;
        if(!unzipRawFile(R.raw.python, sXndroidFile))
            AppModel.fatalError("prepare python fail");
    }

    private static void shellInit()
    {
        String busybox = sXndroidFile + "/busybox";
        if(!new File(busybox).exists())
            prepareRawFile(R.raw.busybox, busybox);
        if(!new File(busybox).setExecutable(true, false)){
            AppModel.fatalError("setExecutable for busybox fail!");
        }
        ShellUtils.init(sXndroidFile);


//        if(!new File(busybox).exists())
//        {
//            File xndroidFile = new File(sXndroidFile);
//            if(!xndroidFile.isDirectory())
//                xndroidFile.mkdirs();
//            writeRawFile(R.raw.busybox,busybox);
//            writeRawFile(R.raw.xndroid_files,gzFile);
//            if(!new File(busybox).setExecutable(true, false)){
//                Log.d("xndroid_debug", "Error:setExecutable fail!");
//            }
//            ShellUtils.init(sXndroidFile);
//            ShellUtils.execBusybox("tar -C "+ sXndroidFile +" -xvf "+gzFile);
//            if(ShellUtils.stdErr !=null || !new File(sXndroidFile + "/xxnet/android_start.py").exists())
//                throw new RuntimeException("unzip file fail!");
//            new File(gzFile).delete();
//        }else {
//            ShellUtils.init(sXndroidFile);
//        }
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
        AppModel.sService = this;
        launch();
        return super.onStartCommand(intent, flags, startId);
    }


    @Override
    public void onDestroy() {
        this.unregisterReceiver(mReceiver);
        sDefaultService = null;
        AppModel.sService = null;
        super.onDestroy();
    }

    private void launch(){
        new WorkingDlg(AppModel.sActivity, sActivity.getString(R.string.xndroid_launching)) {
            @Override
            public void work() {
                updateMsg(sActivity.getString(R.string.request_permission));
                getPermission(sPermissions,sActivity);
                updateMsg(sActivity.getString(R.string.initializing));
                LogUtils.sSetDefaultLog(new LogUtils(sXndroidFile+"/log/java_main.log"));
                LogUtils.i("APP start, sVersionCode: " + sVersionCode + ",sVersionName: " + sVersionName
                        + ",sAutoThread" + sAutoThread + ",sLastVersion" + sLastVersion + ",sDebug" + sDebug
                        + ",sLastFail" + sLastFail + ",sLang" + sLang + ",sXndroidFile" + sXndroidFile);

                checkNetwork();
                checkXndroidUpdate();
                shellInit();
                updateMsg("prepare environment for python...");
                pythonInit();
                updateMsg("prepare environment for fqrouter...");
                FqrouterManager.prepareFqrouter();
                updateMsg("start vpn service, please authorize...");
                FqrouterManager.startVpnService();
                updateMsg("waiting for fqrouter to be ready...");
                FqrouterManager.startFqrouter();
                FqrouterManager.waitReady();
                updateMsg("prepare environment for XX-Net...");
                XXnetManager.prepare();
                updateMsg("waiting for XX-Net to be ready...");
                XXnetManager.startXXnet(LaunchService.this);
                XXnetManager.waitReady();
            }
        };
        regReceiver();
    }

    public static void postStop(){
        FqrouterManager.postStop();
        XXnetService.getDefaultService().postStop();
        for(int i=0;i<10;i++){
            if(FqrouterManager.exitFinished() && XXnetService.getDefaultService().exitFinished())
                break;
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }

//        ShellUtils.close();//AppModle.forceStop need it
        LogUtils.sGetDefaultLog().close();
    }


    @Override
    public IBinder onBind(Intent intent) {
        // TODO: Return the communication channel to the service.
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
