package net.xndroid;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.Intent;
import android.content.SharedPreferences;

public class AutoStart extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        // TODO: This method is called when the BroadcastReceiver is receiving
        // an Intent broadcast.
        SharedPreferences preferences = context.getSharedPreferences("AutoStart", ContextWrapper.MODE_PRIVATE);

        if (intent.getAction().equals("android.intent.action.BOOT_COMPLETED")) {
            //if (preferences.getBoolean("AddToAuto", false)) {
            if (true){
                Intent newIntent = context.getPackageManager()
                        .getLaunchIntentForPackage("net.xndroid");
                newIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                newIntent.putExtra("auto_start", true);
                context.startActivity(newIntent);
            }
        }
    }
}
