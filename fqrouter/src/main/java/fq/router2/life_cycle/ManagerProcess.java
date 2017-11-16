package fq.router2.life_cycle;

import java.io.File;

import fq.router2.MainActivity;
import fq.router2.utils.IOUtils;
import fq.router2.utils.LogUtils;
import fq.router2.utils.ShellUtils;

public class ManagerProcess {

    public static void kill() throws Exception {
        if (ShellUtils.isRooted()) {
            LogUtils.i("run clean");
            try {
                if ("run-needs-su".equals(getRunMode())) {
                    ShellUtils.execute(
                            ShellUtils.pythonEnv(),MainActivity.sFqHome + "/../python/bin/python-launcher.sh",
                            MainActivity.sFqHome + "/manager/main.py", "clean");
                } else {
                    ShellUtils.sudo(
                            ShellUtils.pythonEnv(), MainActivity.sFqHome + "/../python/bin/python-launcher.sh",
                            MainActivity.sFqHome + "/manager/main.py", "clean");
                }
            } catch (Exception e) {
                LogUtils.e("failed to clean", e);
            }
        }
        LogUtils.i("killall python");
        if (new File(MainActivity.sFqHome + "/../busybox").exists()) {
            ShellUtils.sudo(MainActivity.sFqHome + "/../busybox", "killall", "python");
        } else {
            ShellUtils.sudo(ShellUtils.findCommand("killall"), "python");
        }
        for (int i = 0; i < 10; i++) {
            if (exists()) {
                Thread.sleep(3000);
            } else {
                LogUtils.i("killall python done cleanly");
                return;
            }
        }
        LogUtils.e("killall python by force");
        if (new File(MainActivity.sFqHome + "/../busybox").exists()) {
            ShellUtils.sudo(MainActivity.sFqHome + "/../busybox", "killall", "-KILL", "python");
        } else {
            ShellUtils.sudo(ShellUtils.findCommand("killall"), "-KILL", "python");
        }
    }

    public static boolean exists() {
        try {
            String output;
            if (new File(MainActivity.sFqHome + "/../busybox").exists()) {
                output = ShellUtils.sudo(MainActivity.sFqHome + "/../busybox", "killall", "-0", "python");
            } else {
                output = ShellUtils.sudo(ShellUtils.findCommand("killall"), "-0", "python");
            }
            if (output.contains("no process killed")) {
                return false;
            } else {
                return true;
            }
        } catch (Exception e) {
            return false;
        }
    }

    public static String getRunMode() {
//        if (!Deployer.MANAGER_MAIN_PY.exists()) {
//            return "run-normally";
//        }
        File runModeCacheFile = new File(MainActivity.sFqHome + "/etc/run-mode2");
        if (runModeCacheFile.exists()) {
            String cacheContent = IOUtils.readFromFile(runModeCacheFile);
            if ("run-normally".equals(cacheContent)) {
                return "run-normally";
            } else {
                LogUtils.e(cacheContent);
                return "run-needs-su";
            }
        }
        // S4 will fail this test
        try {
            String output = ShellUtils.sudo(ShellUtils.pythonEnv(), MainActivity.sFqHome + "/../python/bin/python-launcher.sh" +
                    " -c \"import subprocess; print(subprocess.check_output(['" +
                    ShellUtils.BUSYBOX_FILE.getCanonicalPath() + "', 'echo', 'hello']))\"").trim();
            LogUtils.i("get run mode: " + output);
            if (output.contains("Permission denied")) {
                IOUtils.writeToFile(runModeCacheFile, "wrong output: " + output);
                return "run-needs-su";
            } else {
                IOUtils.writeToFile(runModeCacheFile, "run-normally");
                return "run-normally";
            }
        } catch (Exception e) {
            LogUtils.e("failed to test subprocess", e);
            IOUtils.writeToFile(runModeCacheFile, "exception: " + e);
            return "run-needs-su";
        }
    }
}
