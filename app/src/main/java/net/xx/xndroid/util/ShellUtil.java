package net.xx.xndroid.util;

import net.xx.xndroid.AppModel;

import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;

public class ShellUtil {
    private static final boolean USE_ROOT = false;
    private static String sBasePath;
    private static String sBusyBox;
    private static Process sProcess;
    private static OutputStreamWriter sInStream;
    private static InputStreamReader sOutStream;
    private static InputStreamReader sErrStream;
    private static int sTaskID = 0;
    private static boolean sRoot = false;
    /**
     * stderr of the last command,null if success
     * */
    static public String stdErr;


    public static boolean isRoot()
    {
        return sRoot;
    }

    private static void checkRoot() {
        sRoot = false;
        char[] buff = new char[1024];
        try {
            Process process = Runtime.getRuntime().exec("su");
            OutputStreamWriter output = new OutputStreamWriter(process.getOutputStream());
            InputStreamReader input = new InputStreamReader(process.getInputStream());
            String testStr = "ROOT_TEST";
            output.write("echo " + testStr + "\n");
            output.flush();
            output.write("exit\n");
            output.flush();
            process.waitFor();
            int count = input.read(buff);
            if (count > 0) {
                if (new String(buff, 0, count).startsWith(testStr))
                    sRoot = true;
            }
        }catch (Exception e){
            e.printStackTrace();
        }
    }

    private static void start()
    {
        if(sProcess != null)
            return;
        LogUtil.defaultLogWrite("info","ShellUtil start, root=" + sRoot);
        try {
            sProcess = Runtime.getRuntime().exec(sRoot ? "su" : sBusyBox + " sh");
            sInStream = new OutputStreamWriter(sProcess.getOutputStream());
            sOutStream = new InputStreamReader(sProcess.getInputStream());
            sErrStream = new InputStreamReader(sProcess.getErrorStream());
        } catch (IOException e) {
            e.printStackTrace();
            stdErr = "init LogUnit fail:" + e.toString();
            LogUtil.defaultLogWrite("error", stdErr);
            AppModel.showToast(stdErr);
        }

        LogUtil.defaultLogWrite("info","ShellUtil is ready");
    }

    public static void init(String basePath)
    {
        sBasePath = basePath;
        sBusyBox = basePath + "/busybox";
        if(USE_ROOT)
            checkRoot();
        start();
    }

    public static void close()
    {
        if(sProcess!=null) {
            try {
                sInStream.close();
                sOutStream.close();
                sErrStream.close();
            }catch(IOException e){
                e.printStackTrace();
            }
            sProcess.destroy();
            sProcess = null;
            sInStream = null;
            sOutStream = null;
            sErrStream = null;
        }

    }

    static public String exec(String cmd)
    {
        return exec(cmd, true);
    }


    static synchronized private String exec(String cmd, boolean wait)//remember synchronized
    {
        LogUtil.defaultLogWrite("ShIn",cmd);
        StringBuffer strBuff = new StringBuffer();
        stdErr = null;
        String finishFlag = "~~~SHELL_TASK_"+sTaskID+"_FINISHED~~~";
        sTaskID++;
        int flagLength = finishFlag.length();
        String task = cmd+"\necho "+finishFlag+"\n";//remember '\n'
        try {
            int count ;
            sInStream.write(task);
            sInStream.flush();
            if(!wait)
                return "";
            char[] buff = new char[1024*64];
            while (true) {
                count = sOutStream.read(buff);
                if (count > 0) {
                    strBuff.append(buff, 0, count);
                    //LogUtil.defaultLogWrite("debug","<SHDEBUG>" + strBuff.toString());
                    int searchBegin = strBuff.length() - count - flagLength;
                    if(searchBegin<0)
                        searchBegin = 0;
                    if(strBuff.indexOf(finishFlag,searchBegin)>=0)
                        break;
                }
            }
            if(sErrStream.ready()) {
                count = sErrStream.read(buff);
                if (count > 0) {
                    stdErr = new String(buff, 0, count);
                    LogUtil.defaultLogWrite("ShErr",stdErr);
                }
            }
            strBuff.delete(strBuff.length() - flagLength - 1,strBuff.length());
            String outStr = strBuff.toString();
            LogUtil.defaultLogWrite("ShOut",outStr);
            return outStr;
        } catch (IOException e) {
            e.printStackTrace();
            LogUtil.defaultLogWrite("error","command readwrite fail:" + e.getMessage());
            stdErr = "exec fail:"+e.toString();
            return "";
        }
    }

    static public String execBusybox(String cmd){
        return exec(sBusyBox + " " + cmd);
    }

}
