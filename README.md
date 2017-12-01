# Xndroid
A proxy software for Android based on XX-Net and fqrouter.

基于XX-Net与fqrouter的Android端代理软件, 完美结合XX-Net与fqrouter, 并支持teredo.

## 特性
 * 集成XX-Net 3.7.16(版本号可自动更新)
 * 集成fqrouter, 实现真正的全局代理
 * 为fqrouter添加teredo支持, XX-Net + IPV6 自由浏览无障碍
 * 为fqrouter添加sock5支持, 方便使用 X_tunnel
 * 调用证书安装器安装证书, 确认即可一键安装(如果已经设置过图案解锁,却要求输入凭证,先清除屏幕锁即可)
 * 监听电量, 网络, 休眠状态, 自动调整最大扫描线程数
 * 集成LightningBrowser 4.5.1, 默认使用 localhost:8087 代理, 关闭证书警告
 * 将XX-Net目录放到应用数据目录(/data/data/net.xndroid), 避免误删, 卸载自动删除


## 感谢以下开源项目
 * [XX-Net](https://github.com/XX-net/XX-Net)
 * [fqrouter (GPL v3.0)](https://github.com/fqrouter/fqrouter)
 * [fqsocks](https://github.com/fqrouter/fqsocks)
 * [fqdns](https://github.com/fqrouter/fqdns)
 * [LightningBrowser](https://github.com/anthonycr/Lightning-Browser)