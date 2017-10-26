package net.xx.xndroid.util;

import android.util.Log;

import net.xx.xndroid.AppModel;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.LinkedList;
import java.util.Queue;

public class LogUtil {
    class LogThread extends Thread
    {
        private boolean mRunning = true;

        void close(){mRunning = false;}

        @Override
        public void run() {
            byte[] buf;
            while(true) {
                if(!mRunning)
                    break;
                if(mOutputStream==null)
                    break;
                checkSize();
                try {
                    synchronized(mBuffer) {
                        if (mBuffer.size() == 0) {
                            mOutputStream.flush();
                            mBuffer.wait();
                        }
                        assert mBuffer.size() > 0;
                        buf = mBuffer.poll().getBytes();
                    }
                    if(mOutputStream == null)
                        return;
                    mOutputStream.write(buf);
                } catch (InterruptedException e) {
                    mRunning = false;
                    e.printStackTrace();
                } catch (IOException e) {
                    mRunning = false;
                    e.printStackTrace();
                }

            }
        }
    }

    private String mPath;
    private Queue<String> mBuffer = new LinkedList<>();
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

        } catch (FileNotFoundException e) {
            e.printStackTrace();
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
        if(tag == null)
            tag = "";
        String time = new SimpleDateFormat("HH:mm:ss").format(new Date());
        String logstr = String.format("[%s %7s] %s\n",time,tag,log);
        Log.d("xndroid_log", logstr);
        synchronized(mBuffer){
            mBuffer.add(logstr);
            mBuffer.notify();
        }
    }

    public void close()
    {
        if(mThread != null) {
            mThread.close();
            logWrite("info","LogUtil exiting");//logThread my be sleeping, write this log to awake it.
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

    public LogUtil(String path, long logSize)
    {
        mLogSize = logSize;
        mPath = path;
        start();
    }

    public LogUtil(String path)
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
            if(!dir.isDirectory())
                dir.mkdir();
            mOutputStream = new FileOutputStream(mPath,true);
            mOutputStream.write(("\n[   info] LogUtil start at " + new Date().toString()
                    + " write to " + mPath + "\n").getBytes());
        } catch (Exception e) {
            e.printStackTrace();
            AppModel.showToast("error:LogUtil write fail." + e.getMessage());
        }
        mThread = new LogThread();
        mThread.start();
    }

    private static LogUtil sDefaultLog;

    public static LogUtil sGetDefaultLog()
    {
        return sDefaultLog;
    }

    public static void sSetDefaultLog(LogUtil log )
    {
        sDefaultLog = log;
    }

    public static void defaultLogWrite(String tag,String log)
    {
        if(sDefaultLog == null)
            throw new IllegalStateException("not set default log yet!");

        sDefaultLog.logWrite(tag, log);

    }
}

