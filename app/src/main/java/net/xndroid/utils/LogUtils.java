package net.xndroid.utils;

import android.util.Log;

import net.xndroid.AppModel;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.PrintStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.LinkedList;
import java.util.Queue;

public class LogUtils {
    class LogThread extends Thread
    {
        private boolean mRunning = true;

        void close(){mRunning = false;}

        @Override
        public void run() {
            byte[] buf;
            while(true) {
                try {
                    if(!mRunning)
                        break;
                    if(mOutputStream==null)
                        break;
                    checkSize();

                    synchronized(mBuffer) {
                        if (mBuffer.size() == 0) {
                            mOutputStream.flush();
                            mBuffer.wait();
                        }
                        if(mBuffer.size() <= 0){
                            Log.e("xndroid_log", "mBuffer.size() <= 0 after wait");
                            mRunning = false;
                            break;
                        }
                        buf = mBuffer.poll().getBytes();
                    }
                    if(mOutputStream == null)
                        return;
                    mOutputStream.write(buf);
                } catch (Exception e) {
                    mRunning = false;
                    e.printStackTrace();
                }

            }
        }
    }

    private String mPath;
    private final Queue<String> mBuffer = new LinkedList<>();
    private File mFile;
    private long mLogSize = 2*1024*1024;
    private FileOutputStream mOutputStream;
    private LogThread mThread;

    private void copyBottom(String path, String newPath, long len)
    {
        File file = new File(path);
        File newFile = new File(newPath);
        long fileLen = file.length();
        FileInputStream input = null;
        FileOutputStream output = null;
        try {
            input = new FileInputStream(file);
            output = new FileOutputStream(newFile);
            output.getChannel().transferFrom(input.getChannel(),fileLen - len , len);

        } catch (IOException e) {
            e.printStackTrace();
        }
        finally {
             try {
                 if(input != null) input.close();
                 if(output != null) output.close();
            } catch (IOException e) {
                e.printStackTrace();
            }

        }
    }

    private void checkSize()
    {
        long len = mFile.length();
        if(len> mLogSize)
        {
            String newPath = mPath+"_tmp";
            try {
                mOutputStream.close();
                mOutputStream.flush();
                mOutputStream=null;
                copyBottom(mPath, newPath, mLogSize/2);
                File file = new File(mPath);
                file.delete();
                new File(newPath).renameTo(file);
                mOutputStream = new FileOutputStream(mPath,true);
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    public void logWrite(String tag,String log)
    {
        if(mOutputStream==null)
            return;
        if(mBuffer.size() > 500) {
            Log.w("xndroid_log", "too many logs in the buffer, drop his log:\n" + log);
            return;
        }
        if(tag == null)
            tag = "";
        String time = new SimpleDateFormat("HH:mm:ss").format(new Date());
        String logstr = String.format("[%s %7s] %s\n",time,tag,log);
//        Log.d("xndroid_log", logstr);
        synchronized(mBuffer){
            mBuffer.add(logstr);
            mBuffer.notify();
        }
    }

    public void close()
    {
        if(mThread != null) {
            mThread.close();
            Log.i("xndroid_log", "LogUtils close");
            logWrite("INFO","LogUtils exiting");//logThread my be sleeping, write this log to awake it.
            mThread = null;
        }
        if(mOutputStream != null) {
            try {
                mOutputStream.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
            mOutputStream = null;
        }
    }

    public LogUtils(String path, long logSize)
    {
        mLogSize = logSize;
        mPath = path;
        start();
    }

    public LogUtils(String path)
    {
        mPath = path;
        start();
    }


    private void start()
    {
        if(mThread != null)
            return;
        mFile = new File(mPath);
        try {
            File dir = new File(mPath).getParentFile();
            if(!dir.exists())
                dir.mkdirs();
            mOutputStream = new FileOutputStream(mPath,true);
            mOutputStream.write(("\n[   INFO] LogUtils start at " + new Date().toString()
                    + " write to " + mPath + "\n").getBytes());
        } catch (Exception e) {
            e.printStackTrace();
            AppModel.showToast("error:LogUtils write fail." + e.getMessage());
        }
        mThread = new LogThread();
        mThread.start();
    }

    private static LogUtils sDefaultLog;

    public static LogUtils sGetDefaultLog()
    {
        return sDefaultLog;
    }

    public static void sSetDefaultLog(LogUtils log )
    {
        sDefaultLog = log;
    }

    public static void defaultLogWrite(String tag,String log)
    {
        if(sDefaultLog == null)
            throw new IllegalStateException("not set default log yet!");

        sDefaultLog.logWrite(tag, log);

    }
    public static void i(String msg)
    {
        Log.i("xndroid_log", msg);
        defaultLogWrite("INFO", msg);
    }

    public static void d(String msg)
    {
        Log.d("xndroid_log", msg);
        if(AppModel.sDebug || AppModel.sLastFail) {
            defaultLogWrite("DEBUG", msg);
        }
    }
    public static void w(String msg)
    {
        Log.w("xndroid", msg);
        defaultLogWrite("WARNING", msg);
    }

    public static void e(String msg)
    {
        Log.e("xndroid_log", msg);
        defaultLogWrite("ERROR", msg);
    }

    public static void e(String msg, Throwable exception)
    {
        Log.e("xndroid_log", msg, exception);
        defaultLogWrite("ERROR", msg + "\n" + formatException(exception));
    }

    private static String formatException(Throwable e) {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        PrintStream ps = new PrintStream(output);
        e.printStackTrace(ps);
        ps.close();
        return output.toString();
    }

}

