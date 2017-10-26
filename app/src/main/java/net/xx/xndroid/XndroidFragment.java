package net.xx.xndroid;

import android.app.AlertDialog;
import android.app.Fragment;
import android.content.DialogInterface;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.security.KeyChain;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;

import net.xx.xndroid.util.LogUtil;
import net.xx.xndroid.util.ShellUtil;
import net.xx.xndroid.xxnet.XXnetAttribute;

import java.io.BufferedInputStream;
import java.io.FileInputStream;

import static net.xx.xndroid.AppModel.PER_AUTO_THREAD;
import static net.xx.xndroid.AppModel.sPreferences;

public class XndroidFragment extends Fragment implements View.OnClickListener
{
    private View mRootView;
    private TextView mAppid;
    private TextView mIpNum;
    private TextView mIpQuality;
    private TextView mXXState;
    private TextView mXXVersion;
    private Runnable mUiUpdate;

    private TextView mProxySet;
    private TextView mCertSet;
    private Switch mAutoScanSet;
    private TextView mAppIdSet;

    private View mConfigTip;
    private View mThreadTip;
    private View mXXnetTip;
    private View mBrowserTip;
    private View mCertTip;
    private View mImportIp;

    @Override
    public void onResume() {
        super.onResume();
        AppModel.sUpdateInfoUI = mUiUpdate;
    }

    @Override
    public void onPause() {
        super.onPause();
        AppModel.sUpdateInfoUI = null;
    }

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container,
                             Bundle savedInstanceState) {
        if(mRootView !=null )
            return mRootView;
        mRootView = inflater.inflate(R.layout.fragment_xndroid, container, false);
        mAppid = (TextView) mRootView.findViewById(R.id.xndroid_appid);
        mIpNum = (TextView) mRootView.findViewById(R.id.xndroid_ip_num);
        mIpQuality = (TextView) mRootView.findViewById(R.id.xndroid_ip_quality);
        mXXState = (TextView) mRootView.findViewById(R.id.xndroid_xxnet_state);
        mXXVersion = (TextView) mRootView.findViewById(R.id.xndroid_xxnet_version);

        mConfigTip = mRootView.findViewById(R.id.xndroid_config_tip);
        mThreadTip = mRootView.findViewById(R.id.xndroid_thread_tip);
        mXXnetTip = mRootView.findViewById(R.id.xndroid_xxnet_tip);
        mBrowserTip = mRootView.findViewById(R.id.xndroid_browser_tip);
        mCertTip = mRootView.findViewById(R.id.xndroid_cert_tip);
        mImportIp = mRootView.findViewById(R.id.xndroid_import_ip);

        mUiUpdate = new Runnable() {
            @Override
            public void run() {
                if(XXnetAttribute.sAppid.length() == 0)
                    mAppid.setText(R.string.public_appid);
                else
                    mAppid.setText(XXnetAttribute.sAppid);
                mIpNum.setText(XXnetAttribute.sIpNum + "");
                mIpQuality.setText(XXnetAttribute.sIpQuality + "");
                mXXVersion.setText(XXnetAttribute.sXXversion);
                mXXState.setText(XXnetAttribute.sStateSummary);
                if(XXnetAttribute.sSummaryLevel == XXnetAttribute.SUMMARY_LEVEL_OK){
                    mXXState.setBackgroundColor(0xFFB3F6B8);
                }else if(XXnetAttribute.sSummaryLevel == XXnetAttribute.SUMMARY_LEVEL_WARNING){
                    mXXState.setBackgroundColor(0xFFFFF4AB);
                }else if(XXnetAttribute.sSummaryLevel == XXnetAttribute.SUMMARY_LEVEL_ERROR){
                    mXXState.setBackgroundColor(0xFFFFC0C0);
                }
            }
        };
        mUiUpdate.run();

        mProxySet = mRootView.findViewById(R.id.xndroid_proxy);
        mCertSet = mRootView.findViewById(R.id.xndroid_cert);
        mAutoScanSet = mRootView.findViewById(R.id.xndroid_auto_thread);
        mAppIdSet = mRootView.findViewById(R.id.xndroid_set_appid);

        if(sPreferences.getBoolean(PER_AUTO_THREAD, true))
            mAutoScanSet.setChecked(true);
        else
            mAutoScanSet.setChecked(false);

        mProxySet.setOnClickListener(this);
        mCertSet.setOnClickListener(this);
        mAutoScanSet.setOnClickListener(this);
        mAppIdSet.setOnClickListener(this);

        mConfigTip.setOnClickListener(this);
        mThreadTip.setOnClickListener(this);
        mXXnetTip.setOnClickListener(this);
        mBrowserTip.setOnClickListener(this);

        mCertTip.setOnClickListener(this);
        mImportIp.setOnClickListener(this);

        return mRootView;
    }

    private void showDlg(String Title, String content){
        new AlertDialog.Builder(AppModel.sActivity)
                .setTitle(Title).setMessage(content)
                .setPositiveButton(R.string.ok, null).create().show();
    }

    private void doProxyset(){
        if(!ShellUtil.isRoot()){
            new AlertDialog.Builder(AppModel.sActivity)
                    .setTitle(R.string.proxy_setting).setMessage(R.string.proxy_setting_tip)
                    .setPositiveButton(R.string.ok, null)
                    .setNeutralButton(R.string.help, new DialogInterface.OnClickListener() {
                        @Override
                        public void onClick(DialogInterface dialog, int which) {
                            AppModel.sActivity.launchUrl("https://github.com/XX-net/XX-Net/wiki/%E5%AE%89%E5%8D%93%E7%89%88");
                        }
                    })
                    .create().show();
        }

    }

    private void doCertSet(){
        String certPath = AppModel.sXndroidFile + "/xxnet/data/gae_proxy/CA.crt";
        byte[] keychain;
        try{
            BufferedInputStream input =new BufferedInputStream(new FileInputStream(certPath));
            keychain = new byte[input.available()];
            input.read(keychain);
        }catch (Exception e){
            e.printStackTrace();
            LogUtil.defaultLogWrite("error", "read certificate fail!");
            return;
        }
        Intent installIntent = KeyChain.createInstallIntent();
        //Android支持两种证书文件格式，一种是PKCS12，一种是X.509证书
        installIntent.putExtra(KeyChain.EXTRA_CERTIFICATE, keychain);
        installIntent.putExtra(KeyChain.EXTRA_NAME,"XX-net Chain");
        startActivityForResult(installIntent, 2);
    }

    private void doAutoScanSet(){
        boolean checked = mAutoScanSet.isChecked();
        if(checked)
            AppModel.sAutoThread = true;
        else{
            AppModel.sAutoThread = false;
            new Thread(new Runnable() {
                @Override
                public void run() {
                    XXnetAttribute.setThreadNum(XXnetService.MAX_THREAD_NUM*2/3);
                }
            }).start();
        }
        AppModel.sPreferences.edit().putBoolean(AppModel.PER_AUTO_THREAD, checked).commit();
    }

    private void doAppIdSet(){
        final EditText editText = new EditText(AppModel.sActivity);
        editText.setText(XXnetAttribute.sAppid);
        new AlertDialog.Builder(AppModel.sActivity)
                .setTitle(R.string.appid_setting).setView(editText)
                .setPositiveButton(R.string.ok, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        final String appId = editText.getText().toString();
                        //Warning! Network request is not allowed to run in main thread.
                        new Thread(new Runnable() {
                            @Override
                            public void run() {
                                XXnetAttribute.setAppid(appId);
                            }
                        }).start();

                    }
                }).setNeutralButton(R.string.help, new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                AppModel.sActivity.launchUrl("https://github.com/XX-net/XX-Net/wiki/how-to-create-my-appids");
            }
        }).create().show();
    }

    private void doConfigTip(){
        showDlg(getString(R.string.global_connfig), getString(R.string.config_tip));
    }

    private void doThreadTip(){
        showDlg(getString(R.string.auto_scan), getString(R.string.auto_scan_tip));
    }

    private void doXXnetTip(){
        AppModel.sActivity.showXXnet();
    }

    private void doBrowserTip(){
        AppModel.sActivity.startLightning();
    }

    private void doCertTip(){
        showDlg(getString(R.string.import_cert) ,getString(R.string.import_cert_tip));
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if(requestCode == 1){
            if(data == null)
                return;
            Uri dataCont = data.getData();
            if(dataCont == null)
                return;
            String path = dataCont.getPath();
            if(path == null)
                return;
            XXnetAttribute.import_ip(path);
        }
    }

    private void doImportIp(){
        new AlertDialog.Builder(AppModel.sActivity)
                .setTitle(R.string.import_ip)
                .setMessage(R.string.import_ip_tip)
                .setPositiveButton(R.string.import_title, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                        intent.setType("file/*");
                        startActivityForResult(intent, 1);
                    }
                }).create().show();
    }

    @Override
    public void onClick(View v) {
        if(v == mProxySet){
            doProxyset();
        }else if(v == mCertSet){
            doCertSet();
        }else if(v == mAutoScanSet){
            doAutoScanSet();
        }else if(v == mAppIdSet){
            doAppIdSet();
        }else if(v == mConfigTip){
            doConfigTip();
        }else if(v == mThreadTip){
            doThreadTip();
        }else if(v == mXXnetTip){
            doXXnetTip();
        }else if(v == mBrowserTip){
            doBrowserTip();
        }else if(v == mCertTip){
            doCertTip();
        }else if(v == mImportIp){
            doImportIp();
        }
    }
}
