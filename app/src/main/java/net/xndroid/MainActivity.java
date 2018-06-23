package net.xndroid;

import android.app.AlertDialog;
import android.app.Fragment;
import android.app.FragmentTransaction;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.res.Configuration;
import android.net.Uri;
import android.os.Bundle;
import android.support.design.widget.FloatingActionButton;
import android.support.design.widget.NavigationView;
import android.support.design.widget.Snackbar;
import android.support.v4.view.GravityCompat;
import android.support.v4.widget.DrawerLayout;
import android.support.v7.app.ActionBarDrawerToggle;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.Toolbar;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.CheckBox;
import android.widget.CompoundButton;
import android.widget.Spinner;

import net.xndroid.fqrouter.FqrouterManager;
import net.xndroid.utils.LogUtils;
import net.xndroid.utils.ShellUtils;
import net.xndroid.xxnet.XXnetManager;

import static net.xndroid.fqrouter.FqrouterManager.ASK_VPN_PERMISSION;

public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    private Fragment mXndroidFragment;
    private WebViewFragment mXXnetFragment;
    private WebViewFragment mFqrouterFragment;

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        try {
            if (ASK_VPN_PERMISSION == requestCode) {
                FqrouterManager.onRequestResult(resultCode, this);
            } else {
                super.onActivityResult(requestCode, resultCode, data);
            }
        } catch (Exception e) {
            LogUtils.e("failed to handle onActivityResult", e);
        }
    }

    private AboutFragment mAboutFragment;
    private ViewGroup mRootView;


    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
    }

    @Override
    protected void onPause() {
        super.onPause();
        AppModel.sIsForeground = false;
        AppModel.sUpdateInfoUI = null;
        mXXnetFragment.postPause();
        mFqrouterFragment.postPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        AppModel.sIsForeground = true;
    }

    private void switchFragment(Fragment fragment)
    {
        FragmentTransaction transaction = getFragmentManager().beginTransaction();
        transaction.replace(R.id.content_main, fragment);
        transaction.commit();
    }

    public void postStop(){
        mXXnetFragment.postStop();
        mFqrouterFragment.postStop();
        this.finish();
        AppModel.sActivity = null;
    }

    private void restart(){
        Intent intent = getIntent();
        finish();
        startActivity(intent);
    }

    @Override
    protected void onStart() {
        super.onStart();
    }

    @Override
    protected void onDestroy() {
        AppModel.sActivity = null;
        super.onDestroy();
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if(AppModel.sAppStoped){
            Log.w("xndroid_log", "Xndroid is exiting, restart the activity.");
            restart();
            try {
                Thread.sleep(10000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            return;
        }
        if(AppModel.sContext != null && AppModel.sService == null){
            AppModel.fatalError("error: App is launched but LaunchService exit");
            return;
        }
        AppModel.sActivity = this;
        if(AppModel.sContext == null) {
            AppModel.appInit(getApplicationContext());
        }
        setContentView(R.layout.activity_main);
        Toolbar toolbar = (Toolbar) findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);

        FloatingActionButton fab = (FloatingActionButton) findViewById(R.id.fab);
        fab.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                Snackbar.make(view, "Replace with your own action", Snackbar.LENGTH_LONG)
                        .setAction("Action", null).show();
            }
        });

        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        ActionBarDrawerToggle toggle = new ActionBarDrawerToggle(
                this, drawer, toolbar, R.string.navigation_drawer_open, R.string.navigation_drawer_close);
        drawer.setDrawerListener(toggle);
        toggle.syncState();

        NavigationView navigationView = (NavigationView) findViewById(R.id.nav_view);
        navigationView.setNavigationItemSelectedListener(this);
        if(!AppModel.sEnableXXNet) {
            navigationView.getMenu().removeItem(R.id.nav_xxnet);
            //navigationView.getMenu().removeItem(R.id.nav_lightning);
        }

        mRootView = (ViewGroup) findViewById(R.id.content_main);

        if(mXndroidFragment == null)
            mXndroidFragment = new XndroidFragment();
        if(mXXnetFragment == null) {
            mXXnetFragment = new WebViewFragment();
            mXXnetFragment.setURL("http://127.0.0.1:8085");
        }
        if(mFqrouterFragment == null) {
            mFqrouterFragment = new WebViewFragment();
            mFqrouterFragment.setURL("http://127.0.0.1:" + FqrouterManager.getPort());
        }
        if(mAboutFragment == null)
            mAboutFragment = new AboutFragment();
        switchFragment(mXndroidFragment);

        if(getIntent().getBooleanExtra("auto_start", false))
            moveTaskToBack(true);
    }

    public void launchUrl(String url){
        Intent intent =new Intent(Intent.ACTION_VIEW);
        intent.setData(Uri.parse(url));
        startActivity(intent);
    }

    private void reboot(){
        restart();
        AppModel.appStop();
        try {
            Thread.sleep(10000);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }

    private void clear_cert_cache(){
        ShellUtils.execBusybox("rm -r " + AppModel.sXndroidFile + "/xxnet/data/gae_proxy/certs");
        AppModel.showToast(getString(R.string.restart_tip));
        new Thread(new Runnable() {
            @Override
            public void run() {
                reboot();
            }
        }).start();
    }

    private void updateXXNet(final boolean rmdata){
        new Thread(new Runnable() {
            @Override
            public void run() {
                AppModel.showToast(getString(R.string.wait_for));
                if(XXnetManager.updateXXNet(rmdata)){
                    AppModel.showToast(getString(R.string.restart_tip));
                    reboot();
                }
            }
        }).start();
    }

    private void updateXXNet(){
        new AlertDialog.Builder(AppModel.sActivity)
                .setTitle(R.string.xxnet_update_title)
                .setMessage(R.string.xxnet_update_tip)
                .setNegativeButton(R.string.update_remove, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        updateXXNet(true);
                    }
                }).setPositiveButton(R.string.update, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        updateXXNet(false);
                    }
                }).create().show();
    }

    private void selectComponent(){
        LayoutInflater inflater = getLayoutInflater();
        View view = inflater.inflate(R.layout.component_setting, null);
        CheckBox checkXXNet = view.findViewById(R.id.launch_check_xxnet);
        CheckBox checkTeredo = view.findViewById(R.id.launch_check_teredo);
        CheckBox checkFqDNS = view.findViewById(R.id.launch_check_fqdns);
        final CheckBox checkAutoTeredo = view.findViewById(R.id.launch_check_teredo_ipv6);
        final CheckBox checkNotification = view.findViewById(R.id.launch_check_notify);
        CheckBox checkAutoStart = view.findViewById(R.id.launch_check_auto_start);
        Spinner spinnerLaunch = view.findViewById(R.id.launch_mode);
        Spinner spinnerNotify = view.findViewById(R.id.launch_notify_mode);

        boolean enableXXnet = AppModel.sPreferences.getBoolean(AppModel.PRE_ENABLE_XXNET, true);
        boolean enableFqDNS = AppModel.sPreferences.getBoolean(AppModel.PRE_ENABLE_FQDNS, true);
        boolean enableTeredo = AppModel.sPreferences.getBoolean(AppModel.PRE_ENABLE_TEREDO, true);
        boolean autoTeredo = AppModel.sPreferences.getBoolean(AppModel.PRE_AUTO_TEREDO, true);
        boolean enableNotification = AppModel.sPreferences.getBoolean(AppModel.PRE_ENABLE_NOTIFICATION, true);
        boolean autoStart = AppModel.sPreferences.getBoolean(AppModel.PRE_AUTO_START, false);

        spinnerLaunch.setSelection(AppModel.sPreferences.getInt(LaunchService.PER_ROOT_MODE, 0));
        spinnerLaunch.setEnabled(ShellUtils.isRoot());
        spinnerNotify.setSelection(AppModel.sPreferences
                .getInt(UpdateManager.PER_UPDATE_POLICY, UpdateManager.UPDATE_ALL));

        checkXXNet.setChecked(enableXXnet);
        checkFqDNS.setChecked(enableFqDNS);
        checkTeredo.setChecked(enableTeredo);
        checkAutoTeredo.setChecked(autoTeredo);
        checkAutoTeredo.setEnabled(enableTeredo);
        checkNotification.setChecked(enableNotification);
        checkNotification.setEnabled(enableXXnet);
        checkAutoStart.setChecked(autoStart);

        checkXXNet.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                checkNotification.setEnabled(isChecked);
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_ENABLE_XXNET, isChecked).apply();
            }
        });
        checkFqDNS.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_ENABLE_FQDNS, isChecked).apply();
            }
        });
        checkTeredo.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                checkAutoTeredo.setEnabled(isChecked);
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_ENABLE_TEREDO, isChecked).apply();
            }
        });
        checkAutoTeredo.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_AUTO_TEREDO, isChecked).apply();
            }
        });
        checkNotification.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_ENABLE_NOTIFICATION, isChecked).apply();
            }
        });
        checkAutoStart.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                AppModel.sPreferences.edit().putBoolean(AppModel.PRE_AUTO_START, isChecked).apply();
            }
        });
        spinnerLaunch.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                AppModel.sPreferences.edit().putInt(LaunchService.PER_ROOT_MODE, position).apply();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {

            }
        });
        spinnerNotify.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                AppModel.sPreferences.edit().putInt(UpdateManager.PER_UPDATE_POLICY, position).apply();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {

            }
        });

        new AlertDialog.Builder(AppModel.sActivity)
                .setTitle(R.string.launch_component)
                .setView(view)
                .setPositiveButton(R.string.reboot_app, new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        new Thread(new Runnable() {
                            @Override
                            public void run() {
                                reboot();
                            }
                        }).start();
                    }
                })
                .setNegativeButton(R.string.ok, null)
                .create().show();
    }

    @Override
    public void onBackPressed() {
        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        if (drawer.isDrawerOpen(GravityCompat.START)) {
            drawer.closeDrawer(GravityCompat.START);
        } else {
            super.onBackPressed();
        }
    }

    @Override
    public boolean onPrepareOptionsMenu(Menu menu) {
        int[] rootActions = new int[]{R.id.action_import_sys_cert, R.id.action_remove_sys_cert};
        for(int id : rootActions){
            MenuItem item = menu.findItem(id);
            if(item != null)
                item.setEnabled(ShellUtils.isRoot());
        }
        int[] xxnetActions = new int[]{R.id.action_update_xxnet, R.id.action_import_cert, R.id.action_import_sys_cert
                                        , R.id.action_remove_sys_cert, R.id.action_clear_cert};
        if(!AppModel.sEnableXXNet) {
            for (int id : xxnetActions) {
                MenuItem item = menu.findItem(id);
                if (item != null)
                    menu.removeItem(id);
            }
        }
        //menu.findItem(R.id.action_update_xxnet).setEnabled(AppModel.sEnableXXNet);
        return true;
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        // Inflate the menu; this adds items to the action bar if it is present.
        getMenuInflater().inflate(R.menu.xndroid_main, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Handle action bar item clicks here. The action bar will
        // automatically handle clicks on the Home/Up button, so long
        // as you specify a parent activity in AndroidManifest.xml.
        int id = item.getItemId();

        //noinspection SimplifiableIfStatement
        if (id == R.id.action_export_log) {
            AppModel.exportLogs();
        }else if(id == R.id.action_import_cert){
            XXnetManager.importCert();
        }else if(id == R.id.action_check_update){
            new Thread(new Runnable() {
                @Override
                public void run() {
                    AppModel.showToast(getString(R.string.getting_version));
                    UpdateManager.checkUpdate(true);
                }
            }).start();
        }else if(id == R.id.action_exit){
            AppModel.appStop();
        }else if(id == R.id.action_clear_cert){
            clear_cert_cache();
        }else if(id == R.id.action_import_sys_cert){
            XXnetManager.importSystemCert();
        }else if(id == R.id.action_remove_sys_cert){
            new Thread(new Runnable() {
                @Override
                public void run() {
                    XXnetManager.cleanSystemCert();
                }
            }).start();
        }else if(id == R.id.action_update_xxnet){
            updateXXNet();
        }else if(id == R.id.action_launch_component){
            selectComponent();
        }else {
            return super.onOptionsItemSelected(item);
        }
        return true;
    }

    public void showXXnet(){
        switchFragment(mXXnetFragment);
    }

    public void showFqrouter(){
        switchFragment(mFqrouterFragment);
    }

    public void startLightning(){
        Intent intent = new Intent(AppModel.sContext, acr.browser.lightning.MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
    }


    @SuppressWarnings("StatementWithEmptyBody")
    @Override
    public boolean onNavigationItemSelected(MenuItem item) {
        // Handle navigation view item clicks here.
        int id = item.getItemId();

        if (id == R.id.nav_about) {
            switchFragment(mAboutFragment);
        } else if (id == R.id.nav_xndroid) {
            switchFragment(mXndroidFragment);
        } else if (id == R.id.nav_xxnet) {
            switchFragment(mXXnetFragment);
        } else if (id == R.id.nav_exit){
            AppModel.appStop();
        } else if (id == R.id.nav_lightning){
            startLightning();
        } else if (id == R.id.nav_fqrouter){
            switchFragment(mFqrouterFragment);
        }

        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        drawer.closeDrawer(GravityCompat.START);
        return true;
    }
}
