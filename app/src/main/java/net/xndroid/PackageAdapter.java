package net.xndroid;

import android.app.Activity;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.CheckBox;
import android.widget.ImageView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;


public abstract class PackageAdapter extends BaseAdapter {
    private List<PackageInfo> mPkgList;
    private Activity mActive;
    private PackageManager mPackageManager;

    public PackageAdapter(Activity activity) {
        super();
        mActive = activity;
        mPackageManager = mActive.getPackageManager();
        mPkgList = mPackageManager.getInstalledPackages(0);

        Collections.sort(mPkgList, new Comparator<PackageInfo>() {
            @Override
            public int compare(PackageInfo o1, PackageInfo o2) {
                ApplicationInfo app1 = o1.applicationInfo;
                ApplicationInfo app2 = o2.applicationInfo;
                String name1 = "";
                String name2 = "";
                if(app1 != null) {
                    name1 = app1.loadLabel(mPackageManager).toString();
                }
                if(app2 != null) {
                    name2 = app2.loadLabel(mPackageManager).toString();
                }

                return name1.compareTo(name2);
            }
        });

        String myPkg = activity.getPackageName();
        // move the selected package to the top and remove the self package
        List<PackageInfo> selectedPkg = new ArrayList<>();
        Iterator<PackageInfo> iterator = mPkgList.iterator();
        while (iterator.hasNext()) {
            PackageInfo info = iterator.next();

            if(myPkg.equals(info.packageName)) {
                iterator.remove();
            }else if(isPackageChecked(info.packageName)) {
                selectedPkg.add(info);
                iterator.remove();
            }
        }

        for(PackageInfo info : selectedPkg) {
            mPkgList.add(0, info);
        }
    }

    @Override
    public int getCount() {
        return mPkgList.size();
    }

    @Override
    public Object getItem(int position) {
        return mPkgList.get(position);
    }

    @Override
    public long getItemId(int position) {
        return position;
    }

    abstract boolean isPackageChecked(String packageName);
    abstract void onPackageChecked(String packageName, boolean checked);

    @Override
    public View getView(int position, View convertView, ViewGroup parent) {
        View  view = convertView;
        if(null == view){
            view = mActive.getLayoutInflater().inflate(R.layout.package_view, parent, false);
        }

        final PackageInfo info = mPkgList.get(position);
        ImageView image = view.findViewById(R.id.proxy_list_icon);
        TextView name = view.findViewById(R.id.proxy_list_name);
        TextView pkg = view.findViewById(R.id.proxy_list_pkg);
        CheckBox check = view.findViewById(R.id.proxy_list_check);

        final String packageName = info.packageName;
        pkg.setText(packageName);
        check.setChecked(isPackageChecked(packageName));
        check.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                PackageAdapter.this.onPackageChecked(packageName, ((CheckBox)v).isChecked());
            }
        });

        ApplicationInfo app = info.applicationInfo;
        if(app != null) {
            image.setImageDrawable(app.loadIcon(mPackageManager));
            name.setText(app.loadLabel(mPackageManager));
        }else{
            image.setImageResource(R.mipmap.ic_logo);
            name.setText(packageName);
        }

        return view;
    }
}
