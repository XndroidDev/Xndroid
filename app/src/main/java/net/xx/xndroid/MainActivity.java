package net.xx.xndroid;

import android.app.Fragment;
import android.app.FragmentTransaction;
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
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;

public class MainActivity extends AppCompatActivity
        implements NavigationView.OnNavigationItemSelectedListener {

    private Fragment mXndroidFragment;
    private XXnetFragment mXXnetFragment;
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
        mXXnetFragment.postPause();
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
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if(AppModel.sAppStoped){
            Log.d("xndroid", "Xndroid is exiting, restart the activity.");
            restart();
            try {
                Thread.sleep(8000);
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            return;
        }
        if(AppModel.sActivity == null)
            AppModel.appInit(this);
        AppModel.sActivity = this;
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

        mRootView = (ViewGroup) findViewById(R.id.content_main);

        if(mXndroidFragment == null)
            mXndroidFragment = new XndroidFragment();
        if(mXXnetFragment == null)
            mXXnetFragment = new XXnetFragment();
        if(mAboutFragment == null)
            mAboutFragment = new AboutFragment();
        switchFragment(mXndroidFragment);
    }

    public void launchUrl(String url){
        Intent intent =new Intent(Intent.ACTION_VIEW);
        intent.setData(Uri.parse(url));
        AppModel.sActivity.startActivity(intent);
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
    public boolean onCreateOptionsMenu(Menu menu) {
        // Inflate the menu; this adds items to the action bar if it is present.
        getMenuInflater().inflate(R.menu.xndroid_main, menu);
        return false;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        // Handle action bar item clicks here. The action bar will
        // automatically handle clicks on the Home/Up button, so long
        // as you specify a parent activity in AndroidManifest.xml.
        int id = item.getItemId();

        //noinspection SimplifiableIfStatement
        if (id == R.id.action_settings) {
            return true;
        }

        return super.onOptionsItemSelected(item);
    }

    public void showXXnet(){
        switchFragment(mXXnetFragment);
    }

    public void startLightning(){
        Intent intent = new Intent(this, acr.browser.lightning.MainActivity.class);
        this.startActivity(intent);
    }

    public void startFqrouter(){
        Intent intent = new Intent(this, fq.router2.MainActivity.class);
        this.startActivity(intent);
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
            startFqrouter();
        }

        DrawerLayout drawer = (DrawerLayout) findViewById(R.id.drawer_layout);
        drawer.closeDrawer(GravityCompat.START);
        return true;
    }
}
