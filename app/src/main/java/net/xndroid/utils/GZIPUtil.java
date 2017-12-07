package net.xndroid.utils;

/**
* This source file is from  http://www.cnblogs.com/lbjz/p/4008458.html
* original package name is com.yabsz.decompCompr
* */


import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.apache.commons.compress.utils.IOUtils;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.List;

/**
 * @Title: GZIPUtil.java
 * @Description: gzip文件压缩和解压缩工具类
 * @author LM
 * @date 2009-11-4 下午06:23:29
 * @version V1.0
 */
public class GZIPUtil {

    /**
     *
     * @Title: pack
     * @Description: 将一组文件打成tar包
     * @param sources
     *            要打包的原文件数组
     * @param target
     *            打包后的文件
     * @return File 返回打包后的文件
     * @throws
     */
    public static File pack(List<File> sources, File target) {
        FileOutputStream out = null;
        try {
            out = new FileOutputStream(target);
        } catch (FileNotFoundException e1) {
            e1.printStackTrace();
        }
        TarArchiveOutputStream os = new TarArchiveOutputStream(out);
        for (File file : sources) {
            try {
                System.out.println(file.getName());
                os.putArchiveEntry(new TarArchiveEntry(file));
                IOUtils.copy(new FileInputStream(file), os);
                os.closeArchiveEntry();

            } catch (FileNotFoundException e) {
                e.printStackTrace();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
        if (os != null) {
            try {
                os.flush();
                os.close();
            } catch (IOException e) {
                e.printStackTrace();
            }
        }

        return target;
    }
}