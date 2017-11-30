package net.xndroid;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.os.BatteryManager;

import net.xndroid.utils.LogUtils;


public class XndroidReceiver extends BroadcastReceiver {

    private final int BATTERY_LOW_LIMIT = 30;

    private void handleBattery(Intent intent){
        int level=intent.getIntExtra(BatteryManager.EXTRA_LEVEL,0);
        int scale=intent.getIntExtra(BatteryManager.EXTRA_SCALE,0);
        int levelPercent = (int)(((float)level / scale) * 100);
        boolean charging = intent.getIntExtra(BatteryManager.EXTRA_STATUS,
                BatteryManager.BATTERY_STATUS_UNKNOWN) == BatteryManager.BATTERY_STATUS_CHARGING;
        if(levelPercent < BATTERY_LOW_LIMIT && !charging)
            AppModel.sDevBatteryLow = true;
        else
            AppModel.sDevBatteryLow = false;
        LogUtils.i("battery:" + level +"%, BatteryLow=" + AppModel.sDevBatteryLow);
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if(action == Intent.ACTION_BATTERY_CHANGED){
            handleBattery(intent);
        }else if(action == ConnectivityManager.CONNECTIVITY_ACTION){
            AppModel.checkNetwork();
        }else if(action == Intent.ACTION_SCREEN_ON){
            AppModel.sDevScreenOff = false;
            LogUtils.i("screen on");
        }else if(action == Intent.ACTION_SCREEN_OFF){
            AppModel.sDevScreenOff = true;
            LogUtils.i("screen off");
        }
    }
}
