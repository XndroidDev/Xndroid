package net.xndroid;

import android.app.ProgressDialog;
import android.content.Context;


public class WorkingDlg extends ProgressDialog {

    public WorkingDlg(Context context ,String title) {
        super(context);
        this.setTitle(title);
        this.setIndeterminate(true);
        this.setCancelable(false);
    }

    //public abstract void work();
    public void start(final Runnable work)
    {
        this.show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                work.run();
                cancel();
            }
        }).start();
    }

    public void updateMsg(final String msg)
    {
        if(null == AppModel.sActivity)
            return;
        AppModel.sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                WorkingDlg.this.setMessage(msg);
            }
        });
    }

    public static void updateMsg(String msg, WorkingDlg dlg)
    {
        if(dlg != null)
            dlg.updateMsg(msg);
    }

}
