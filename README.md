# Xndroid
A proxy software for Android based on XX-Net and fqrouter.

[最新测试版](https://raw.githubusercontent.com/XndroidDev/Xndroid-update/master/update/app-debug.apk)

[稳定版1.2.6](https://github.com/XndroidDev/Xndroid/releases/download/1.2.6/app-release.apk) 

[稳定版1.1.9](https://github.com/XndroidDev/Xndroid/releases/download/1.1.9/app-release.apk)

[稳定版1.1.7](https://github.com/XndroidDev/Xndroid/releases/download/1.1.7/app-release.apk)

[稳定版1.1.6](https://github.com/XndroidDev/Xndroid/releases/download/1.1.6/app-release.apk)

基于XX-Net与fqrouter的Android端代理软件, XX-Net与fqrouter各取所长, 内置teredo客户端.

## 特性
 * 集成XX-Net 3.13.1(版本号可自动更新)
 * 集成fqrouter, 实现全局代理
 * 为fqrouter添加teredo支持, XX-Net + IPV6 自由浏览无障碍
 * 调用证书安装器安装证书, 确认即可一键安装(如果已经设置过图案解锁,却要求输入凭证,先清除屏幕锁即可), root后可导入为系统证书
 * 监听电量, 网络, 休眠状态, 自动调整最大扫描线程数
 * 集成LightningBrowser 4.5.1, 关闭证书警告

## 兼容性与局限性
 * 目前不支持X86架构.
 * Android 4.0 以下系统不支持VpnService, 暂不能使用本应用.
 * __Android 7.0及以上可能出现导入证书后仍然不被信任的情况. 建议在chrome, firefox(须在浏览器中导入证书), 或可忽略证书警告的浏览器(如:内置LightningBrowser, X浏览器)中使用. 如果root了, 就可以导入为系统证书, 默认被信任.__
 * __注意一些APP(如 Twitter, Facebook 等)由于不信任GAE的证书,可能无法正常访问网络, 建议在浏览器中使用.__
 * 手动更新XX-Net后出现一次`XX-Net异常退出`属正常现象.

## 共享代理网络
 fqrouter提供了多种网络共享功能, root后可使用更多功能. **注意如果用到了GAE代理, 则目标设备上也需安装证书**
 * HTTP 代理, 如果目标设备支持http代理且在同一局域网下, 就可使用此项功能共享代理网络. 可使用fqrouter的2516端口(需先在fqrouter开启`HTTP代理`), GAE 的8087 端口, 或X-Tunnel 的1080端口 ,XX-Net Smart Router 的8086端口
 * 如果以root模式启动, 可使用Android 的网络共享功能, 如: 便携式热点, USB共享网络(一些手机上可能导致死机), 蓝牙共享网络
 * 如果以root模式启动, 可使用fqrouter 的 Pick&Play 功能 , 通过类似于 `中间人攻击` 的手法时局域网中其他设备走fqrouter的代理
 * 如果以root模式启动, 部分手机可以使用 fqrouter的 wifi-repeat(无线中继) 功能, 其它设备连上即可自由浏览. 注意fqrouter早已停止维护此功能, 无法保证此功能在所有手机上都可以, 并且不会尝试增强此功能的兼容性

## 直连白名单
 fqrouter已内置大量国内域名列表和国内ip段, 对绝大部分国内网站的访问会直连. 你也可以在`/sdcard/domain_whitelist.txt`(若不存在新建即可)中添加自定义的需要直连的域名, 每行一个, 如:
```
github.com
githubusercontent.com
githubapp.com
ftchinese.com
ted.com
tedcdn.com
howcast.com
```
 注意Android6.0 及以上必须授予`存储空间(访问媒体文件)`的权限. 如果仍然不能满足需求, 可以在fqrouter的`配置代理`中关闭`优先使用个人代理`, 并开启`直连可以直连的服务器`

## 关于修改XX-NET配置
一般无需也不建议手动修改XX-NET配置文件. 如特殊情况需要修改, root用户可直接修改相关文件, 其位于`/data/data/net.xndroid/files/xndroid_files/xxnet/`; 非root用户可以[下载XX-NET zip压缩包](https://github.com/XX-net/XX-Net/releases), 将其解压, 并修改或添加相应文件再压缩回zip, 点击菜单中的`离线更新XX-NET`, 选择修改的zip文件即可.

## 关于编译
编译使用AndroidStudio, 并在AndroidStudio中安装相应SDK, 如API Level 23. 由于VPN模式下需使用JNI, 故还需在AndroidStuio中安装NDK. NDK版本不要太高, 否则不支持armeabi指令集. 此外, LightningBrowser编译还需要在AndroidStudio中安装API Level 26及Kotlin插件.
编译前,在源码顶层目录(Unix环境)下执行`./fqrouter_prebulid.sh`. 其会将fqrouter使用gz压缩到`app/src/main/res/raw/fqrouter`. 下载XX-Net源码, 将`android_start.py`复制到XX-Net源码顶级目录, 然后使用gz压缩到`app/src/main/res/raw/xxnet`.

```sh
# 编译器前进行以下操作
# 进入源码目录
cd "Xndroid_source_path"
# 压缩fqrouter
./fqrouter_prebulid.sh
# 下载XX-Net到临时目录
mkdir xxnet_tmp
version=3.12.2
wget -O xxnet_tmp/xxnet.zip https://github.com/XX-net/XX-Net/archive/${version}.zip
unzip xxnet_tmp/xxnet.zip -d xxnet_tmp
cp android_start.py xxnet_tmp/XX-Net-${version}
# 移除不必要的文件
rm -r xxnet_tmp/XX-Net-${version}/code/default/gae_proxy/server
mv xxnet_tmp/XX-Net-${version}/code/default/python27/1.0 xxnet_tmp/XX-Net-${version}/code/default/python27/0
mkdir -p xxnet_tmp/XX-Net-${version}/code/default/python27/1.0/lib
cp -r xxnet_tmp/XX-Net-${version}/code/default/python27/0/lib/noarch xxnet_tmp/XX-Net-${version}/code/default/python27/1.0/lib/
rm -r xxnet_tmp/XX-Net-${version}/code/default/python27/0
# 更改版本号
mv xxnet_tmp/XX-Net-${version}/code/default xxnet_tmp/XX-Net-${version}/code/${version}
echo ${version} > xxnet_tmp/XX-Net-${version}/code/version.txt
# 压缩XX-Net
mv xxnet_tmp/XX-Net-${version} xxnet_tmp/xxnet
tar -czf app/src/main/res/raw/xxnet xxnet_tmp/xxnet
rm -r xxnet_tmp
```

## 感谢以下开源项目
 * [XX-Net](https://github.com/XX-net/XX-Net)
 * [fqrouter (GPL v3.0)](https://github.com/fqrouter/fqrouter)
 * [fqsocks](https://github.com/fqrouter/fqsocks)
 * [fqdns](https://github.com/fqrouter/fqdns)
 * [LightningBrowser](https://github.com/anthonycr/Lightning-Browser)
