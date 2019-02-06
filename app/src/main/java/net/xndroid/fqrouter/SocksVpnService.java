package net.xndroid.fqrouter;

import android.app.PendingIntent;
import android.content.Intent;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.net.VpnService;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;
import android.os.ParcelFileDescriptor;
import android.widget.Toast;

import net.xndroid.AppModel;
import net.xndroid.LaunchService;
import net.xndroid.MainActivity;
import net.xndroid.R;
import net.xndroid.utils.LogUtils;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileDescriptor;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.lang.reflect.Field;
import java.net.ConnectException;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;


/**
 * android:process="net.xndroid.fqrouter.sockvpnservice"
 * Do not run this service with activities in the same process
 * or fds of webview may be closed in error when call garbageCollectFds
 *
 * */

/**
 * A wrong address will be given when call socket.recvfrom in python, if the sock is create in java thread.
 * So create UDP socket in jni if necessary
 *
 * */

public class SocksVpnService extends VpnService {

    static {
        System.loadLibrary("sockvpn");
    }

    ExecutorService executorService;

    private native int sendFd(int sock_fd, int send_fd);
    private native int createUdpFd();

    private static ParcelFileDescriptor tunPFD;
    private static String sFqHome;
    private static String sXndroidFile;
    private static boolean stopFlag = true;
    private static int sProxyMode = 0;
    private static String[] sProxyList;
    private Set<String> skippedFds = new HashSet<String>();
    private Set<Integer> stagingFds = new HashSet<Integer>();

    public static final int MSG_STOP_VPN = 1;

    /**
     * Handler of incoming messages from clients.
     */
    class SockHandler extends Handler {
        @Override
        public void handleMessage(Message msg) {
            switch (msg.what) {
                case MSG_STOP_VPN:
                    SocksVpnService.this.onRevoke();
                    break;
                default:
                    super.handleMessage(msg);
            }
        }
    }


    @Override
    public IBinder onBind(Intent intent) {
        Messenger messenger = new Messenger(new SockHandler());
        return messenger.getBinder();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        stopFlag = false;
        sXndroidFile = getFilesDir().getAbsolutePath() + "/xndroid_files";
        sFqHome = sXndroidFile + "/fqrouter";
        LogUtils.sSetDefaultLog(new LogUtils(sXndroidFile+"/log/java_vpn.log"));
        LogUtils.i("sockVpnService start");
        executorService = Executors.newFixedThreadPool(16);
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    listenFdServerSocket();
                } catch (Exception e) {
                    LogUtils.e("fdsock failed " + e, e);
                }
            }
        }).start();

        sProxyMode = intent.getIntExtra("proxy_mode", 0);
        sProxyList = intent.getStringArrayExtra("proxy_list");
        LogUtils.i("sProxyMode=" + sProxyMode + ",sProxyList=" + (sProxyList!=null?sProxyList:"null"));

        String ipv6 = intent.getStringExtra("origin_ipv6");
        if(ipv6!=null){
            startVpn(null);
            LogUtils.i("origin ipv6 " + ipv6);
        }

        return START_NOT_STICKY;
    }


    @Override
    public void onRevoke() {
        stopService(new Intent(this, LaunchService.class));
        stopSelf();
        stopVpn();
    }


    private void showToast(final String msg){
        try {
            Handler handler = new Handler(Looper.getMainLooper());
            handler.post(new Runnable() {
                @Override
                public void run() {
                    Toast.makeText(getApplicationContext(), msg, Toast.LENGTH_LONG).show();
                }
            });
        }
        catch (Exception e){
            LogUtils.e("show toast error", e);
        }

    }


    @Override
    public void onDestroy() {
        stopVpn();
        if(LogUtils.sGetDefaultLog() != null)
            LogUtils.sGetDefaultLog().close();
    }

    private void startVpn(String teredo_ip) {

        try {
            LogUtils.i("startVpn, teredo_ip is " + teredo_ip);
            Intent statusActivityIntent = new Intent(this, MainActivity.class);
            PendingIntent pIntent = PendingIntent.getActivity(this, 0, statusActivityIntent, 0);
            Builder builder = new Builder().setConfigureIntent(pIntent).setSession("fqrouter2");
            if(Build.VERSION.SDK_INT < 20){
                builder = builder.addAddress("10.25.1.1", 30);
            }else {
                builder = builder.addAddress("26.26.26.1", 30);
            }
            if(teredo_ip != null){
                builder = builder.addAddress(teredo_ip, 120)
                        .setMtu(1280)
                        .addRoute("::", 0);
            }

            if(sProxyMode == AppModel.PROXY_MODE_NONE) {
                LogUtils.i("do ipv4 router because global proxy is disabled");

            } else {

                builder = builder.addRoute("1.0.0.0", 8)
                        .addRoute("2.0.0.0", 7)
                        .addRoute("4.0.0.0", 6)
                        .addRoute("8.0.0.0", 7)
                        // 10.0.0.0 - 10.255.255.255
                        .addRoute("11.0.0.0", 8)
                        .addRoute("12.0.0.0", 6)
                        .addRoute("16.0.0.0", 4)
                        .addRoute("32.0.0.0", 3)
                        .addRoute("64.0.0.0", 2)
                        .addRoute("139.0.0.0", 8)
                        .addRoute("140.0.0.0", 6)
                        .addRoute("144.0.0.0", 4)
                        .addRoute("160.0.0.0", 5)
                        .addRoute("168.0.0.0", 6)
                        .addRoute("172.0.0.0", 12)
                        // 172.16.0.0 - 172.31.255.255
                        .addRoute("172.32.0.0", 11)
                        .addRoute("172.64.0.0", 10)
                        .addRoute("172.128.0.0", 9)
                        .addRoute("173.0.0.0", 8)
                        .addRoute("174.0.0.0", 7)
                        .addRoute("176.0.0.0", 4)
                        .addRoute("192.0.0.0", 9)
                        .addRoute("192.128.0.0", 11)
                        .addRoute("192.160.0.0", 13)
                        // 192.168.0.0 - 192.168.255.255
                        .addRoute("192.169.0.0", 16)
                        .addRoute("192.170.0.0", 15)
                        .addRoute("192.172.0.0", 14)
                        .addRoute("192.176.0.0", 12)
                        .addRoute("192.192.0.0", 10)
                        .addRoute("193.0.0.0", 8)
//                    .addRoute("194.0.0.0", 7)
//                    .addRoute("196.0.0.0", 6)
//                    .addRoute("200.0.0.0", 5)
//                    .addRoute("208.0.0.0", 4)
//                    .addRoute("224.0.0.0", 4)
//                    .addRoute("240.0.0.0",5)
//                    .addRoute("248.0.0.0",6)
//                    .addRoute("252.0.0.0",7)
//                    .addRoute("254.0.0.0",8)
                        .addDnsServer("8.8.8.8");
                for (int i = 194; i < 224; i++) {
                    builder = builder.addRoute(i + ".0.0.0", 8);
                }

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP && sProxyList != null) {
                    if (sProxyMode == AppModel.PROXY_MODE_BACKLIST) {
                        for (String pkg : sProxyList) {
                            try {
                                builder.addDisallowedApplication(pkg);
                            } catch (Exception e) {
                                LogUtils.e("addDisallowedApplication for " + pkg + "failed", e);
                            }
                        }
                    } else if (sProxyMode == AppModel.PROXY_MODE_WHITELIST) {
                        for (String pkg : sProxyList) {
                            try {
                                builder.addAllowedApplication(pkg);
                            } catch (Exception e) {
                                LogUtils.e("addAllowedApplication for " + pkg + "failed", e);
                            }
                        }
                    }
                }
            }

            tunPFD = builder.establish();
            if (tunPFD == null) {
                LogUtils.e("vpn establish fail");
                stopSelf();
                return;
            }
            final int tunFD = tunPFD.getFd();
            LogUtils.i("tunFD is " + tunFD );
            LogUtils.i("Started in VPN mode");

        } catch (Exception e) {
            LogUtils.e("VPN establish failed", e);
        }
    }

    private void listenFdServerSocket() throws Exception {
        final LocalServerSocket fdServerSocket = new LocalServerSocket("fdsock2");
        initSkippedFds();
        try {
            int count = 0;
            while (!stopFlag) {
                try {
                    final LocalSocket fdSocket = fdServerSocket.accept();
                    executorService.submit(new Runnable() {
                        @Override
                        public void run() {
                            try {
                                passFileDescriptor(fdSocket);
                            } catch (Exception e) {
                                LogUtils.e("failed to handle fdsock or message", e);
                            }
                        }
                    });
                    count += 1;
                    if (count % 200 == 0) {
                        garbageCollectFds();
                    }
                } catch (Exception e) {
                    LogUtils.e("failed to handle fdsock", e);
                }
            }
            executorService.shutdown();
        } finally {
            fdServerSocket.close();
        }
    }

    private void garbageCollectFds() {
        if (listFds() == null || listFds().length == 0) {
            LogUtils.e("can not gc fd as can not list them");
        } else {
            closeStagingFds();
        }
    }

    private String[] listFds() {
        String[] fdlist = new File("/proc/self/fd").list();
        if(fdlist != null)
            return fdlist;
        try {
            Process mProcess = Runtime.getRuntime().exec(sXndroidFile + "/busybox ls /proc/self/fd");
            mProcess.waitFor();
            byte[] output = new byte[10240];
            int readLen = mProcess.getInputStream().read(output);
            return new String(output, 0, readLen).split("\\s+");
        }catch (Exception e){
            LogUtils.e("listFds fail", e);
        }

        return new String[]{};
    }

    private void initSkippedFds() {
        String[] fileNames = listFds();
        LogUtils.i("init skipped fd count: " + fileNames.length);
        Collections.addAll(skippedFds, fileNames);
    }

    private void closeStagingFds() {
        int count = 0;
        for (int stagingFd : stagingFds) {
            try {
                if (isSocket(stagingFd)) {
                    ParcelFileDescriptor.adoptFd(stagingFd).close();
                    count += 1;
                }
            } catch (Exception e) {
                LogUtils.d("close stagingFd " + stagingFd +" fail: " + e.toString());
            }
        }
        LogUtils.i("closed fd count: " + count);
        stagingFds.clear();
        String[] fileNames = listFds();
        LogUtils.i("current total fd count: " + fileNames.length);
        for (String fileName : fileNames) {
            if (skippedFds.contains(fileName)) {
                continue;
            }
            try {
                if (isSocket(fileName)) {
                    stagingFds.add(Integer.parseInt(fileName));
                }
            } catch (Exception e) {
                skippedFds.add(fileName);
                LogUtils.d("add stagingFd " + fileName + " fail: " + e.toString());
                continue;
            }
        }
    }

    private boolean isSocket(Object fileName) throws IOException {
        return new File("/proc/self/fd/" + fileName).getCanonicalPath().contains("socket:");
    }


    private void passFileDescriptor(LocalSocket fdSocket) throws Exception {
        OutputStream outputStream = fdSocket.getOutputStream();
        InputStream inputStream = fdSocket.getInputStream();
        try {
            BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream), 1);
            String request = reader.readLine();
            String[] parts = request.split(",");
            if ("TUN".equals(parts[0])) {
                if(tunPFD == null)
                    outputStream.write('!');
                else {
                    fdSocket.setFileDescriptorsForSend(new FileDescriptor[]{tunPFD.getFileDescriptor()});
                    outputStream.write('*');
                    LogUtils.i("send TUN fd");
                }
            } else if ("PING".equals(parts[0])) {
                OutputStreamWriter outputStreamWriter = new OutputStreamWriter(outputStream);
                outputStreamWriter.write("PONG");
                outputStreamWriter.close();
            } else if ("OPEN UDP".equals(parts[0])) {
                passUdpFileDescriptor(fdSocket, outputStream, false);
            } else if ("OPEN PERSIST UDP".equals(parts[0])) {
                passUdpFileDescriptor(fdSocket, outputStream, true);
            } else if ("OPEN TCP".equals(parts[0])) {
                String dstIp = parts[1];
                int dstPort = Integer.parseInt(parts[2]);
//                int connectTimeout = Integer.parseInt(parts[3]);
                int connectTimeout = (int)Float.parseFloat(parts[3]);
                passTcpFileDescriptor(fdSocket, outputStream, dstIp, dstPort, connectTimeout);
            } else if ("TEREDO READY".equals(parts[0])) {
                if(tunPFD == null) {
                    this.startVpn(parts[1]);
                }else {
                    LogUtils.e("receive message 'TEREDO READY', but tunPFD is not null" );
                }
            } else if ("TEREDO FAIL".equals(parts[0])) {
                LogUtils.e("start teredo fail");
                showToast(getString(R.string.teredo_fail));
                if(tunPFD == null) {
                    this.startVpn(parts[1]);
                }else{
                    LogUtils.e("receive message 'TEREDO FAIL', but tunPFD is not null" );
                }
            } else {
                throw new UnsupportedOperationException("fdsock unable to handle: " + request);
            }
        } finally {
            try {
                inputStream.close();
            } catch (Exception e) {
                LogUtils.e("failed to close input stream", e);
            }
            try {
                outputStream.close();
            } catch (Exception e) {
                LogUtils.e("failed to close output stream", e);
            }
            fdSocket.close();
        }
    }

    private void passTcpFileDescriptor(
            LocalSocket fdSocket, OutputStream outputStream,
            String dstIp, int dstPort, int connectTimeout) throws Exception {
        Socket sock = new Socket();
        sock.setTcpNoDelay(true); // force file descriptor being created
        try {
            ParcelFileDescriptor fd = ParcelFileDescriptor.fromSocket(sock);
            if (protect(fd.getFd())) {
                try {
                    sock.connect(new InetSocketAddress(dstIp, dstPort), connectTimeout);
                    try {
                        fdSocket.setFileDescriptorsForSend(new FileDescriptor[]{fd.getFileDescriptor()});
                        outputStream.write('*');
                        outputStream.flush();
                    } finally {
                        sock.close();
                        fd.close();
                    }
                } catch (ConnectException e) {
                    LogUtils.e("connect " + dstIp + ":" + dstPort + " failed");
                    outputStream.write('!');
                } catch (SocketTimeoutException e) {
                    LogUtils.e("connect " + dstIp + ":" + dstPort + " failed");
                    outputStream.write('!');
                } finally {
                    outputStream.flush();
                }
            } else {
                LogUtils.e("protect tcp socket failed");
            }
        } finally {
            sock.close();
        }
    }

    public static String byteArrayToHexStr(byte[] byteArray) {
        if (byteArray == null){
            return null;
        }
        char[] hexArray = "0123456789ABCDEF".toCharArray();
        char[] hexChars = new char[byteArray.length * 2];
        for (int j = 0; j < byteArray.length; j++) {
            int v = byteArray[j] & 0xFF;
            hexChars[j * 2] = hexArray[v >>> 4];
            hexChars[j * 2 + 1] = hexArray[v & 0x0F];
        }
        return new String(hexChars);
    }

    private void passUdpFileDescriptor(LocalSocket fdSocket, OutputStream outputStream, boolean persist) throws Exception {
        DatagramSocket sock = null;
        ParcelFileDescriptor fd = null;
        int nativeFd = 0;
        try {
            if(persist)
                nativeFd = createUdpFd();
            else
            {
                sock = new DatagramSocket();
                fd = ParcelFileDescriptor.fromDatagramSocket(sock);
                nativeFd = fd.getFd();
            }
            if(nativeFd <=2) {
                LogUtils.e("create udp socket fail");
                return;
            }

            if (protect(nativeFd)) {
                if(persist){
                    LogUtils.i("create a persistent udp socket");
                    skippedFds.add("" + nativeFd);
                    Field privateFd = FileDescriptor.class.getDeclaredField("descriptor");
                    privateFd.setAccessible(true);
                    int connectFd = privateFd.getInt(fdSocket.getFileDescriptor());
                    sendFd(connectFd, nativeFd);
                }
                else {
                    fdSocket.setFileDescriptorsForSend(new FileDescriptor[]{fd.getFileDescriptor()});
                    outputStream.write('*');
                    outputStream.flush();
                }
            } else {
                LogUtils.e("protect udp socket failed");
            }
        } finally {
            if(sock != null)
                sock.close();
            if(fd != null)
                fd.close();
            if(persist && nativeFd > 2)
                ParcelFileDescriptor.adoptFd(nativeFd).close();
        }
    }

    private void stopVpn() {
        stopFlag = true;
        LogUtils.d("stopVpn called");
        if (tunPFD != null) {
            try {
                tunPFD.close();
            } catch (IOException e) {
                LogUtils.e("failed to stop tunPFD", e);
            }
            tunPFD = null;
        }
    }
}

