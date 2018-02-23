package net.xndroid;

import android.app.Fragment;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import net.xndroid.xxnet.XXnetManager;

public class AboutFragment extends Fragment {

    private View mRootView;
    private TextView mVersionView;
    private TextView mXXnetVersion;
    private View mUpdateView;

    @Override
    public void onResume() {
        super.onResume();
        mXXnetVersion.setText("XX-Net    " + XXnetManager.sXXversion);
    }

    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, Bundle savedInstanceState) {
        if(mRootView !=null )
            return mRootView;
        mRootView = inflater.inflate(R.layout.fragment_about, container, false);
        mVersionView = mRootView.findViewById(R.id.xndroid_version);
        mVersionView.setText("Xndroid    " + AppModel.sVersionName + (AppModel.sDebug ? " DEBUG" : " RELEASE"));
        mXXnetVersion = mRootView.findViewById(R.id.xndroid_xxnet_version);
        mUpdateView = mRootView.findViewById(R.id.xndroid_check_update);
        mUpdateView.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                new Thread(new Runnable() {
                    @Override
                    public void run() {
                        AppModel.showToast(getString(R.string.getting_version));
                        UpdateManager.checkUpdate(true);
                    }
                }).start();
            }
        });
        return mRootView;
    }
}
