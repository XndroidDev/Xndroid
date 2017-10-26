# Xndroid
XX-Net的Android深度适配版本.

## 特性
 * 集成XX-Net 3.6.7(版本号会自动更新)
 * 集成LightningBrowser 4.5.1, 默认使用 localhost:8087 代理, 关闭证书警告, 无需任何配置即可直接使用
 * 将XX-Net目录放到应用数据目录(/data/data/net.xx.xndroid), 避免误删, 卸载自动删除
 * 使用前台服务, 避免意外退出(部分机型可能仍然强制结束进程,需要根据各机型的特点设置.如MIUI在最近应用列表中锁定)
 * 监听电量, 网络, 休眠状态, 自动调整最大扫描线程数
 * 将语言地区信息添加到环境变量, 避免XX-Net启动时显示为英文
 * 调用证书管理器安装证书, 确认即可一键安装(如果已经设置过图案解锁,却要求输入凭证,先清除屏幕锁即可)

## 感谢以下项目
 * [XX-Net](https://github.com/XX-net/XX-Net)
 * [LightningBrowser](https://github.com/anthonycr/Lightning-Browser)