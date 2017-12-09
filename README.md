# Xndroid
A proxy software for Android based on XX-Net and fqrouter.

[测试版本(Android8.0下载这个)](https://raw.githubusercontent.com/XndroidDev/Xndroid/master/update/app-debug.apk)
[最新版本 1.1.1](https://github.com/XndroidDev/Xndroid/releases/download/1.1.1/app-release.apk)

基于XX-Net与fqrouter的Android端代理软件, 完美结合XX-Net与fqrouter, 并支持teredo.

## 特性
 * 集成XX-Net 3.7.16(版本号可自动更新)
 * 集成fqrouter, 实现全局代理
 * 为fqrouter添加teredo支持, XX-Net + IPV6 自由浏览无障碍
 * 为fqrouter添加sock5支持, 方便使用 X_tunnel
 * 调用证书安装器安装证书, 确认即可一键安装(如果已经设置过图案解锁,却要求输入凭证,先清除屏幕锁即可)
 * 监听电量, 网络, 休眠状态, 自动调整最大扫描线程数
 * 集成LightningBrowser 4.5.1, 默认使用 localhost:8087 代理, 关闭证书警告

## 兼容性与局限性
 * Android 4.0(不包括) 以下系统不支持VpnService, 暂不能使用本应用.
 * Android 4.0 ~ Android 6.0.1 仅需确认安装证书, 填上APPID, 即可在顺利浏览器和一些应用顺利使用.部分APP(如 Twitter, Facebook)由于不信任用户导入的证书,可能无法正常访问网络, 建议在浏览器中使用.
 * Android 7.0及以上可能出现导入证书后仍然不被信任的情况,建议在可忽略证书警告的浏览器(如<内置>LightningBrowser, X浏览器), 或可导入证书的浏览器(如firefox)中使用.如果出现"net::ERR_CONTENT_DECODING_FAILED"的错误提示,建议在chrome 或 firefox(可能需要先在浏览器中导入证书) 中使用.

## 感谢以下开源项目
 * [XX-Net](https://github.com/XX-net/XX-Net)
 * [fqrouter (GPL v3.0)](https://github.com/fqrouter/fqrouter)
 * [fqsocks](https://github.com/fqrouter/fqsocks)
 * [fqdns](https://github.com/fqrouter/fqdns)
 * [LightningBrowser](https://github.com/anthonycr/Lightning-Browser)