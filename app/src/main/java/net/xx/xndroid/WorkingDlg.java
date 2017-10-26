package net.xx.xndroid;

import android.app.ProgressDialog;
import android.content.Context;


public abstract class WorkingDlg extends ProgressDialog {
    Context mContex;
    public WorkingDlg(Context context ,String title) {
        super(context);
        this.setTitle(title);
        this.setIndeterminate(true);
        this.setCancelable(false);
        this.show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                work();
                cancel();
            }
        }).start();
    }
    abstract void work();

    public void updataMesg(final String mesg)
    {
        AppModel.sActivity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                WorkingDlg.this.setMessage(mesg);
            }
        });

    }

}
