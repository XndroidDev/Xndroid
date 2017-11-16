package fq.router2;

import android.os.Bundle;
import android.preference.Preference;
import android.preference.PreferenceActivity;

import fq.router2.utils.ShellUtils;

public class MainSettingsActivity extends PreferenceActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        addPreferencesFromResource(R.xml.preferences);
        findPreference("OpenManager").setOnPreferenceClickListener(new Preference.OnPreferenceClickListener() {
            @Override
            public boolean onPreferenceClick(Preference preference) {
                finish();
                return false;
            }
        });
        if (!ShellUtils.checkRooted()) {
            getPreferenceScreen().removePreference(findPreference("AutoLaunchEnabled"));
            getPreferenceScreen().removePreference(findPreference("NotificationEnabled"));
        }
    }

    @Override
    public void onStart() {
        super.onStart();
    }

    @Override
    public void onStop() {
        super.onStop();
    }

    private String _str(int id) {
        return getResources().getString(id);
    }
}
