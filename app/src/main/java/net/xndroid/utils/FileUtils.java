package net.xndroid.utils;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedList;
import java.util.List;
import java.util.ListIterator;

public class FileUtils {

    public static void rm(String path, String[] postfixs){
        LogUtils.i("rm path=" + path +",postfixs=" +
                (postfixs == null ? "null" : Arrays.toString(postfixs)));
        File topFile = new File(path);
        if(!topFile.exists())
            return;
        if(!topFile.isDirectory()) {
            if(postfixs == null) {
                topFile.delete();
                LogUtils.i("delete file:" + topFile.getAbsolutePath());
            }else {
                String[] parts = topFile.getName().split("\\.");
                if(parts.length >= 2)
                    for(String postfix: postfixs)
                        if(postfix.equals(parts[parts.length-1]))
                        {
                            topFile.delete();
                            LogUtils.i("delete file:" + topFile.getAbsolutePath());
                            break;
                        }
            }
            return;
        }
        List<File> toHandle = new LinkedList<>();
        List<File> toDelete = new ArrayList<>();
        toHandle.add(topFile);
        while (toHandle.size() > 0){
            ListIterator<File> iterator = toHandle.listIterator();
            while(iterator.hasNext()){
                File parDir = iterator.next();
                iterator.remove();
                toDelete.add(parDir);
                for(File file : parDir.listFiles()){
                    if(file.isDirectory())
                        iterator.add(file);
                    else {
                        if(postfixs == null) {
                            file.delete();
                            LogUtils.i("delete file:" + file.getAbsolutePath());
                        }
                        else{
                            String[] parts = file.getName().split("\\.");
                            if(parts.length >= 2)
                                for(String postfix: postfixs)
                                    if(postfix.equals(parts[parts.length-1]))
                                    {
                                        file.delete();
                                        LogUtils.i("delete file:" + file.getAbsolutePath());
                                        break;
                                    }
                        }
                    }
                }

            }
        }
        ListIterator<File> iterator = toDelete.listIterator(toDelete.size() - 1);
        while(iterator.hasPrevious())
        {
            File file = iterator.previous();
            if(file.listFiles().length == 0) {
                file.delete();
                LogUtils.i("remove directory: " + file.getAbsolutePath());
            }
        }
    }
}
