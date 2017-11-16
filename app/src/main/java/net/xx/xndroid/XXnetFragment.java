package net.xx.xndroid;

import android.app.Fragment;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

class MyWebViewClient extends WebViewClient {
    //重写shouldOverrideUrlLoading方法，使点击链接后不使用其他的浏览器打开。
    @Override
    public boolean shouldOverrideUrlLoading(WebView view, String url) {
        view.loadUrl(url);
        //如果不需要其他对点击链接事件的处理返回true，否则返回false
        return true;
    }

}


public class XXnetFragment extends Fragment {


    private View mRootView;
    private WebView mWebView;

    @Override
    public void onStart() {
        super.onStart();
        mWebView.onResume();
        mWebView.loadUrl("http://127.0.0.1:8085");
    }

    public void postPause()
    {
        if(mWebView != null)
            mWebView.onPause();
    }

    public void postStop()
    {
        if(mWebView != null)
            mWebView.destroy();
    }

    private void setWebView()
    {

        WebSettings webSettings = mWebView.getSettings();
        webSettings.setJavaScriptEnabled(true);//如果访问的页面中要与Javascript交互，则webview必须设置支持Javascript
        webSettings.setUseWideViewPort(true); //将图片调整到适合webview的大小
        webSettings.setLoadWithOverviewMode(true); // 缩放至屏幕的大小
        webSettings.setSupportZoom(true); //支持缩放，默认为true。是下面那个的前提。
        webSettings.setBuiltInZoomControls(true); //设置内置的缩放控件。若为false，则该WebView不可缩放
        webSettings.setDisplayZoomControls(false); //隐藏原生的缩放控件
        webSettings.setAllowFileAccess(true); //设置可以访问文件
        webSettings.setJavaScriptCanOpenWindowsAutomatically(true); //支持通过JS打开新窗口
        webSettings.setLoadsImagesAutomatically(true); //支持自动加载图片
        webSettings.setDefaultTextEncodingName("utf-8");//设置编码格式
        mWebView.setWebViewClient(new MyWebViewClient());
    }

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container,
                             Bundle savedInstanceState) {
        if(mRootView !=null )
            return mRootView;
        mRootView = inflater.inflate(R.layout.fragment_xxnet, container, false);
        mWebView = (WebView) mRootView.findViewById(R.id.xxnet_webview);
        setWebView();
        return mRootView;
    }

}
