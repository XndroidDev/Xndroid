package net.xndroid;

import android.annotation.TargetApi;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.os.Build;
import android.os.IBinder;

import net.xndroid.fqrouter.FqrouterManager;
import net.xndroid.utils.FileUtils;
import net.xndroid.utils.GZipUtils;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;
import net.xndroid.utils.TarUtils;
import net.xndroid.xxnet.XXnetManager;
import net.xndroid.xxnet.XXnetService;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;

import static android.os.Build.VERSION_CODES.M;
import static net.xndroid.AppModel.sActivity;
import static net.xndroid.AppModel.sContext;
import static net.xndroid.AppModel.sDevMobileWork;
import static net.xndroid.AppModel.sXndroidFile;
import static net.xndroid.AppModel.showToast;


public class LaunchService extends Service {
    public LaunchService() {
    }

    public static final String PER_ROOT = "XNDROID_ROOT";
    public static final String PER_ROOT_MODE = "XNDROID_ROOT_MODE";

    private static LaunchService sDefaultService;

    public static LaunchService getDefaultService(){
        return sDefaultService;
    }

    private static final String[] sPermissions = {
            "android.permission.INTERNET",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.ACCESS_NETWORK_STATE"};

    @TargetApi(M)
    static private void getPermission(String[] permissions,Activity activity) {
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
                showToast(sContext.getString(R.string.permissions_need));
            activity.requestPermissions(preToDo.toArray(new String[preToDo.size()]), 0);
        }
    }



    private static boolean writeRawFile(int id, String destPath) {
        InputStream input = sContext.getResources().openRawResource(id);
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

    public static boolean unzipForO(String dirPath, String srcFile){
        String tarFile = srcFile + ".tar";
        try {
            GZipUtils.decompress(srcFile, tarFile);
            TarUtils.dearchive(tarFile,dirPath);
            new File(tarFile).delete();
        } catch (Exception e) {
            e.printStackTrace();
            return false;
        }

        return true;
    }

    public static boolean unzipRawFile(int fileId, String dirPath){
        String filePath = sXndroidFile + "/tmp-" + fileId + ".tar.gz";
        if(!prepareRawFile(fileId, filePath))
            return false;
        boolean ret = true;
        String out = ShellUtils.execBusybox("tar -C " + dirPath + " -xvf " + filePath);
        if(ShellUtils.stdErr != null || out.length() < 20){
            ret = unzipForO(dirPath, filePath);
        }
        new File(filePath).delete();
        ShellUtils.execBusybox("chmod -R 777 " + dirPath);
        String parts[] = ShellUtils.execBusybox("ls -ldn " + sXndroidFile).split("\\s+");
        if(parts.length < 4){
            LogUtils.e("fail to chown: get uid gid fail");
        }else {
            ShellUtils.execBusybox("chown -R " + parts[2] + " " + dirPath);
            ShellUtils.execBusybox("chgrp -R " + parts[2] + " " + dirPath);
        }
        return ret;
    }

//    private static void test(){
//        LogUtils.i("========================begin test======================");
//        ShellUtils.execBusybox("whoami");
//        ShellUtils.execBusybox("ls -l " + sXndroidFile);
//        ShellUtils.execBusybox("ls -l " + sXndroidFile + "/python");
//        ShellUtils.execBusybox("ls -l " + sXndroidFile + "/python/bin");
//        ShellUtils.execBusybox("du -a " + sXndroidFile);
//        File bin = new File(sXndroidFile + "/python/bin");
//        if(!bin.exists()){
//            LogUtils.e(sXndroidFile + "/python/bin  not exist!");
//        }
//        String[] binstrs = bin.list();
//        if(binstrs == null){
//            LogUtils.e("bin.list() == null");
//        }else {
//            LogUtils.i("binstrs: " + Arrays.toString(binstrs));
//        }
//        File[] binfiles = bin.listFiles();
//        if(binfiles == null){
//            LogUtils.e("binfiles == null");
//        }else {
//            LogUtils.i("binfiles len: " + binfiles.length);
//        }
//        if(new File(sXndroidFile + "/python/bin/python").exists()){
//            LogUtils.i("python/bin/python canExecute:" + new File(sXndroidFile + "/python/bin/python").canExecute());
//        }else {
//            LogUtils.e(sXndroidFile + "/python/bin/python not exist !");
//        }
//        if(!new File(sXndroidFile + "/python/bin/python").setExecutable(true, false)){
//            LogUtils.e("can't set executable");
//        }
//        if(new File(sXndroidFile + "/python/bin/python").exists()){
//            LogUtils.i("python/bin/python canExecute:" + new File(sXndroidFile + "/python/bin/python").canExecute());
//        }else {
//            LogUtils.e(sXndroidFile + "/python/bin/python not exist !");
//        }
//        ShellUtils.execBusybox("ls -l " + sXndroidFile + "/python/bin");
//        LogUtils.i("========================end test======================");
//        AppModel.exportLogs();
//    }

    private static void pythonInit(){
        if(FileUtils.exists(sXndroidFile + "/python/bin/python"))
            return;
        if(!unzipRawFile(R.raw.python, sXndroidFile))
            AppModel.fatalError("prepare python fail");
//        test();
        File[] files = new File(sXndroidFile + "/python/bin").listFiles();
        if(files == null){
            LogUtils.e("fail to list python/bin");
        }else {
            for (File binFile : files) {
                binFile.setExecutable(true, false);
            }
        }
    }

    private static Boolean _modeChosen = null;

    public static void chooseLaunchMode(){
        if(!ShellUtils.isRoot()){
            AppModel.showToast(sContext.getString(R.string.only_vpn_available));
            return;
        }
        sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                new AlertDialog.Builder(AppModel.sActivity)
                    .setTitle(R.string.choose_mode)
                    .setMessage(R.string.choose_mode_tip)
                    .setCancelable(false)
                    .setNegativeButton(R.string.vpn_mode, new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            LaunchService._modeChosen = Boolean.FALSE;
                            AppModel.sPreferences.edit().putInt(PER_ROOT_MODE, -1).apply();
                        }
                    }).setPositiveButton(R.string.root_mode, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        LaunchService._modeChosen = Boolean.TRUE;
                        AppModel.sPreferences.edit().putInt(PER_ROOT_MODE, 1).apply();
                    }
                }).create().show();
            }
        });
    }

    private static boolean isRunInRootMode(){
        if(!ShellUtils.isRoot())
            return false;
        int mode = AppModel.sPreferences.getInt(PER_ROOT_MODE, 0);
        if(AppModel.sLastFail || mode == 0){
            _modeChosen = null;
            chooseLaunchMode();
            while (_modeChosen == null){
                try {
                    Thread.sleep(300);
                } catch (InterruptedException e) {
                    e.printStackTrace();
                }
            }
            if(_modeChosen == Boolean.TRUE)
                return true;
            else
                return false;
        }
        if(mode == 1)
            return true;
        if(mode == -1)
            return false;
        return false;
    }

    private static void shellInit() {
        ShellUtils.init(sXndroidFile);
        try {
            String busybox = sXndroidFile + "/busybox";
            if(!new File(busybox).exists()) {
                if(Build.VERSION.SDK_INT < 26) {
                    prepareRawFile(R.raw.busybox, busybox);
                }else {
                    if(ShellUtils.isRoot()){
                        prepareRawFile(R.raw.busybox, busybox);
                    }else {
                        prepareRawFile(R.raw.busybox_for_o, busybox);
                        new File(sXndroidFile + "/busybox_for_o").createNewFile();
                    }
                }
            }else {
                if(Build.VERSION.SDK_INT >= 26) {
                    boolean busyboxOFlag = new File(sXndroidFile + "/busybox_for_o").exists();
                    if (ShellUtils.isRoot() && busyboxOFlag) {
                        new File(busybox).delete();
                        new File(sXndroidFile + "/busybox_for_o").delete();
                        prepareRawFile(R.raw.busybox, busybox);
                    } else if (!ShellUtils.isRoot() && !busyboxOFlag) {
                        new File(busybox).delete();
                        prepareRawFile(R.raw.busybox_for_o, busybox);
                        new File(sXndroidFile + "/busybox_for_o").createNewFile();
                    }
                }
            }

            if(!new File(busybox).setExecutable(true, false)){
                AppModel.fatalError("setExecutable for busybox fail!");
            }
        }catch (Exception e){
            LogUtils.e("init busybox fail", e);
            AppModel.fatalError("init busybox fail");
        }

        /*for "line 1: dirname: Permission denied" in Android 4.x and Android 5.x*/
        ShellUtils.execBusybox("ln -s " + ShellUtils.sBusyBox + " " + sXndroidFile + "/dirname");
        ShellUtils.exec("export PATH=" + sXndroidFile + ":$PATH");
        /*get device information*/
        ShellUtils.exec("env");
        ShellUtils.exec("getprop");
        if(ShellUtils.isRoot()){
            AppModel.sPreferences.edit().putBoolean(PER_ROOT, true).apply();
            LogUtils.i("run as root");
        }else {
            if(AppModel.sPreferences.getBoolean(PER_ROOT, false)){
                AppModel.showToast(sContext.getString(R.string.no_root_tip));
                LogUtils.w("NO ROOT");
            }
        }
        AppModel.sIsRootMode = isRunInRootMode();
        if(AppModel.sIsRootMode){
            LogUtils.i("launch in root mode");
            AppModel.showToast(sContext.getString(R.string.do_not_force_stop));
        }
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
                    try {
                        /*XX-Net may be not really ready, wait for a moment*/
                        Thread.sleep(4000);
                        UpdateManager.checkUpdate(false);
                    }catch (Exception e){
                        LogUtils.e("checkXndroidUpdate fail", e);
                    }

                }
            }).start();
        }
    }

    private static void clearOldProcess(){
        XXnetManager.quit();
        FqrouterManager.quit();
    }


    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        sDefaultService = this;
        AppModel.sService = this;
        launch();
        return START_NOT_STICKY;
    }


    @Override
    public void onDestroy() {
        this.unregisterReceiver(mReceiver);
        sDefaultService = null;
        if(!AppModel.sAppStoped){
            LogUtils.w("Launch service onDestroy, call appStop");
            AppModel.appStop();
        }
        super.onDestroy();
    }

    private static void updateEnvEarly(){
        if(AppModel.sLastVersion == 0 || AppModel.sLastVersion == AppModel.sVersionCode)
            return;
        if(AppModel.sLastVersion < 13) {
            new File(sXndroidFile + "/busybox").delete();
            new File(sXndroidFile + "/busybox_for_o").delete();
        }
    }

    private static void updataEnv(){
        if(AppModel.sLastVersion == 0 || AppModel.sLastVersion == AppModel.sVersionCode)
            return;
        ShellUtils.execBusybox("rm -r " + sXndroidFile + "/fqrouter");
        if(AppModel.sLastVersion < 13) {
            ShellUtils.execBusybox("rm -r " + sXndroidFile + "/xxnet");
        }
        if(AppModel.sLastVersion < 16){
            ShellUtils.execBusybox("rm -r " + sXndroidFile + "/python");
        }
    }

    private void launch(){
        new WorkingDlg(AppModel.sActivity, getString(R.string.xndroid_launching)) {
            @Override
            public void work() {
                try {
                    updateMsg(getString(R.string.request_permission));
                    getPermission(sPermissions, sActivity);
                    updateMsg(getString(R.string.initializing));
                    clearOldProcess();
                    updateEnvEarly();
                    shellInit();
                    updataEnv();
                    if (ShellUtils.isRoot()) {
                        FqrouterManager.cleanIptables();
                    }
                    if (!XXnetManager.checkNetwork()) {
                        AppModel.fatalError(getString(R.string.no_network_tip));
                    }
                    AppModel.getNetworkState();
                    updateMsg(getString(R.string.prepare_python));
                    pythonInit();
                    updateMsg(getString(R.string.prepare_fqrouter));
                    FqrouterManager.prepareFqrouter();
                    if (!AppModel.sIsRootMode) {
                        updateMsg(getString(R.string.start_vpn));
                        FqrouterManager.startVpnService();
                    }
                    updateMsg(getString(R.string.wait_fqrouter));
                    FqrouterManager.startFqrouter();
                    FqrouterManager.waitReady();
                    updateMsg(getString(R.string.prepare_xxnet));
                    XXnetManager.prepare();
                    updateMsg(getString(R.string.wait_xxnet));
                    XXnetManager.startXXnet(LaunchService.this);
                    XXnetManager.waitReady();
                    checkXndroidUpdate();
                }catch (Exception e){
                    LogUtils.e("launch fail ", e);
                    AppModel.fatalError("unexpected exception: " + e.getMessage());
                }
            }
        };
        regReceiver();
    }

    public static void postStop(){
        FqrouterManager.postStop();
        if(XXnetService.getDefaultService() != null) {
            XXnetService.getDefaultService().postStop();
        }
        for(int i=0;i<10;i++){
            if(FqrouterManager.exitFinished() && XXnetService.getDefaultService().exitFinished())
                break;
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
        }
        ShellUtils.execBusybox("chmod -R 777 " + sXndroidFile);
        if(sDefaultService != null)
            sDefaultService.stopSelf();
//        ShellUtils.close();//AppModle.forceStop need it
    }

    public static void handleFatalError(){
        FqrouterManager.postStop();
        if(XXnetService.getDefaultService() != null){
            XXnetService.getDefaultService().stopXXnet();
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        // TODO: Return the communication channel to the service.
        throw new UnsupportedOperationException("Not yet implemented");
    }
}
