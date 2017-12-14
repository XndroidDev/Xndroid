# Xndroid
A proxy software for Android based on XX-Net and fqrouter.

[最新版](https://raw.githubusercontent.com/XndroidDev/Xndroid/master/update/app-release.apk)

[debug版](https://raw.githubusercontent.com/XndroidDev/Xndroid/master/update/app-debug.apk)

[稳定版1.1.1 (Android8.0无法使用)](https://github.com/XndroidDev/Xndroid/releases/download/1.1.1/app-release.apk)

基于XX-Net与fqrouter的Android端代理软件, 完美结合XX-Net与fqrouter, 并支持teredo.

## 特性
 * 集成XX-Net 3.7.16(版本号可自动更新)
 * 集成fqrouter, 实现全局代理
 * 为fqrouter添加teredo支持, XX-Net + IPV6 自由浏览无障碍
 * 为fqrouter添加sock5支持, 方便使用 X_tunnel
 * 调用证书安装器安装证书, 确认即可一键安装(如果已经设置过图案解锁,却要求输入凭证,先清除屏幕锁即可), root后可导入为系统证书
 * 监听电量, 网络, 休眠状态, 自动调整最大扫描线程数
 * 集成LightningBrowser 4.5.1, 默认使用 localhost:8087 代理, 关闭证书警告

## 兼容性与局限性
 * Android 4.0(不包括) 以下系统不支持VpnService, 暂不能使用本应用.
 * Android 4.0 ~ Android 6.0.1 仅需确认安装证书, 填上APPID, 即可在顺利浏览器和一些应用顺利使用.部分APP(如 Twitter, Facebook)由于不信任用户导入的证书,可能无法正常访问网络, 建议在浏览器中使用.
 * Android 7.0及以上可能出现导入证书后仍然不被信任的情况, 建议在可忽略证书警告的浏览器(如<内置>LightningBrowser, X浏览器), 或可导入证书的浏览器(如firefox)中使用. 如果root了, 就可以导入为系统证书, 默认被信任. 如果出现"net::ERR_CONTENT_DECODING_FAILED"的错误提示,建议在chrome 或 firefox(可能需要先在浏览器中导入证书) 中使用.

## 关于XX-Net版本
 原则上在新版XX-Net值得更新且可完美运行的情况下, Xndroid更新时会尽量使内置XX-Net较新. 因此通常无需在XX-Net中更新. 另外目前XX-Net测试版在Android上运行还有些问题, 请暂时不要将XX-Net更新到测试版

## 共享代理网络
 fqrouter提供了多种网络共享功能, root后可使用更多功能. 注意如果用到了GAE代理, 则目标设备上也需安装证书
 * HTTP 代理, 如果目标设备支持http代理且在同一局域网下, 就可使用此项功能共享代理网络. 可使用fqrouter的2516端口, GAE 的8087 端口, 或X-tunnel 的1080(sock5)端口 
 * 如果以root模式启动, 可使用Android 的网络共享功能, 如: 便携式热点, USB共享网络(一些手机上可能导致死机), 蓝牙共享网络
 * 如果以root模式启动, 可使用fqrouter 的 Pick&Play 功能 , 通过类似于 `中间人攻击` 的手法时局域网中其他设备走fqrouter的代理
 * 如果以root模式启动, 部分手机可以使用 fqrouter的 wifi-repeat(无线中继) 功能, 其它设备连上热点就能自由浏览. 注意fqrouter早已停止维护此功能, 无法保证此功能在所有手机上都可以, 并且不会尝试增强此功能的兼容性

## 感谢以下开源项目
 * [XX-Net](https://github.com/XX-net/XX-Net)
 * [fqrouter (GPL v3.0)](https://github.com/fqrouter/fqrouter)
 * [fqsocks](https://github.com/fqrouter/fqsocks)
 * [fqdns](https://github.com/fqrouter/fqdns)
 * [LightningBrowser](https://github.com/anthonycr/Lightning-Browser)