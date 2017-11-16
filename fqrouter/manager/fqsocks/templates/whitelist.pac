/*
 gfw_whitelist.pac

 GFW Whitelist
 - inspired by autoproxy and chnroutes

 v1.2
 Author: n0gfwall0@gmail.com
 License: MIT License

 */


function FindProxyForURL(url, host)
{
    /* * * * * * * * * * * * * * * * * * * * * * * * * * 
     *                                                 *
     *  一定要换成你的ip地址                           *
     *  Replace your proxy ip-address:port here!!      *
     *                                                 *
     * * * * * * * * * * * * * * * * * * * * * * * * * */

    var ip_address = '{{ http_gateway }}';

    /* * * * * * * * * * * * * * * * * * * * * * * * * * 
     *                                                 *
     * 代理类型 (翻墙一般适用 SOCKS 或 HTTPS)          *
     * Proxy type                                      *
     *                                                 *
     * * * * * * * * * * * * * * * * * * * * * * * * * */
    var proxy_type = 'PROXY'; // or 'SOCKS'

    // HTTPS 是用于 Chrome 的安全代理
    // http://www.chromium.org/developers/design-documents/secure-web-proxy


    /* * * * * * * * * * * * * * * * * * * * * * * * * */
    var proxy = proxy_type + ' ' + ip_address;


    // Avoid calling any functions that might invoke the DNS resoultion.
    var url = url.toLowerCase();
    var host = host.toLowerCase();

    // skip local hosts
    if (isPlainHostName(host)) return 'DIRECT';

    // skip cn domains
    if (shExpMatch(host,"*.cn")) return 'DIRECT';

    // skip ftp
    if (shExpMatch(url, "ftp:*")) return 'DIRECT';

    // check if the ipv4 format (TODO: ipv6)
    //   http://home.deds.nl/~aeron/regex/
    var re_ipv4 = /^\d+\.\d+\.\d+\.\d+$/g;
    if (re_ipv4.test(host)) {
        // in theory, we can add chnroutes test here.
        // but that is probably too much an overkill.
        return 'DIRECT';
    }

    // a very long list. trust chrome will cache the results

    // skip top Chinese sites
    // source: 
    // (1) custom list
    // (2) https://dl-web.dropbox.com/u/3241202/apps/chn-cdn/dnsmasq.server.conf
    // (3) Domestic CDN and cloud
    // (4) alexa 500
    //     less all the cn domains
    //     less google.com.hk, google.com, google.co.uk, googleusercontent.com
    //     google.com.tw, tumblr.com, wikipedia.org, youtube, github, wordpress
    //     wsj.com, godaddy,stackoverflow.com, zaobao.com

    // custom list. feel free to add.
    // mostly ad servers and img servers
    if(
        shExpMatch(host, "(*\.|)kandian.com") ||
            shExpMatch(host, "(*\.|)homeinns.com") ||
            shExpMatch(host, "(*\.|)sinajs.com") ||
            shExpMatch(host, "(*\.|)douban.fm")    ||
            shExpMatch(host, "(*\.|)pixlr.com") ||
            shExpMatch(host, "(*\.|)jing.fm")      ||
            shExpMatch(host, "(*\.|)oadz.com")  ||
            shExpMatch(host, "(*\.|)youshang.com") ||
            shExpMatch(host, "(*\.|)kuaidi100.com") ||
            shExpMatch(host, "(*\.|)sinahk.net")   ||
            shExpMatch(host, "(*\.|)kuaidi100.com") ||
            shExpMatch(host, "(*\.|)adsame.com")   ||
            shExpMatch(host, "(*\.|)scorecardresearch.com") ||
            shExpMatch(host, "(*\.|)imrworldwide.com")||
            shExpMatch(host, "(*\.|)wrating.com") ||
            shExpMatch(host, "(*\.|)mediav.com")   ||
            shExpMatch(host, "(*\.|)lycos.com") ||
            shExpMatch(host, "(*\.|)gamesville.com")||
            shExpMatch(host, "(*\.|)lygo.com") ||
            shExpMatch(host, "(*\.|)quantserve.com")||
            shExpMatch(host, "(*\.|)miaozhen.com")  ||
            shExpMatch(host, "(*\.|)qstatic.com")  ||
            shExpMatch(host, "(*\.|)tremormedia.com")  ||
            shExpMatch(host, "(*\.|)yieldmanager.com")||
            shExpMatch(host, "(*\.|)adsonar.com")  ||
            shExpMatch(host, "(*\.|)adtechus.com") ||
            shExpMatch(host, "(*\.|)bluekai.com")   ||
            shExpMatch(host, "(*\.|)ipinyou.com")  ||
            shExpMatch(host, "(*\.|)bdstatic.com")   ||
            shExpMatch(host, "(*\.|)bdimg.com")    ||
            shExpMatch(host, "(*\.|)mediaplex.com")  ||
            shExpMatch(host, "(*\.|)ykimg.com")    ||
            shExpMatch(host, "(*\.|)irs01.com")  ||
            shExpMatch(host, "(*\.|)irs01.net")    ||
            shExpMatch(host, "(*\.|)mmstat.com")   ||
            shExpMatch(host, "(*\.|)tanx.com")     ||
            shExpMatch(host, "(*\.|)atdmt.com")   ||
            shExpMatch(host, "(*\.|)tudouui.com")  ||
            shExpMatch(host, "(*\.|)tdimg.com")   ||
            shExpMatch(host, "(*\.|)ku6img.com")   ||
            shExpMatch(host, "(*\.|)ku6cdn.com")   ||
            shExpMatch(host, "(*\.|)staticsdo.com")||
            shExpMatch(host, "(*\.|)snyu.com")  ||
            shExpMatch(host, "(*\.|)mlt01.com")    ||
            shExpMatch(host, "(*\.|)doubleclick.net") ||
            shExpMatch(host, "(*\.|)scanscout.com")||
            shExpMatch(host, "(*\.|)betrad.com") ||
            shExpMatch(host, "(*\.|)invitemedia.com")||
            shExpMatch(host, "(*\.|)adroll.com") ||
            shExpMatch(host, "(*\.|)mathtag.com")  ||
            shExpMatch(host, "(*\.|)2mdn.net")  ||
            shExpMatch(host, "(*\.|)rtbidder.net") ||
            shExpMatch(host, "(*\.|)compete.com")  ||
            shExpMatch(host, "(*\.|)vizu.com")     ||
            shExpMatch(host, "(*\.|)adnxs.com")  ||
            shExpMatch(host, "(*\.|)mookie1.com")  ||
            shExpMatch(host, "(*\.|)pubmatic.com")  ||
            shExpMatch(host, "(*\.|)serving-sys.com")||
            shExpMatch(host, "(*\.|)legolas-media.com")||
            shExpMatch(host, "(*\.|)harrenmedianetwork.com")||
            shExpMatch(host, "(*\.|)google-analytics.com")
        ) {

        return 'DIRECT';
    }


    // Chinese cloud
    if(
        shExpMatch(host, "(*\.|)alipayobjects.com") ||
            shExpMatch(host, "(*\.|)aliyun.com") ||
            shExpMatch(host, "(*\.|)alicdn.com")
        ) {
        return 'DIRECT';
    }

    // ihipop's list
    if(
        shExpMatch(host, "(*\.|)renren.com") ||
            shExpMatch(host, "(*\.|)sina.com") ||
            shExpMatch(host, "(*\.|)iask.com") ||
            shExpMatch(host, "(*\.|)cctv*.com") ||
            shExpMatch(host, "(*\.|)img.cctvpic.com") ||
            shExpMatch(host, "(*\.|)163.com") ||
            shExpMatch(host, "(*\.|)netease.com") ||
            shExpMatch(host, "(*\.|)126.net") ||
            shExpMatch(host, "(*\.|)qq.com") ||
            shExpMatch(host, "(*\.|)ptlogin2.qq.com") ||
            shExpMatch(host, "(*\.|)gtimg.com") ||
            shExpMatch(host, "(*\.|)taobao.com") ||
            shExpMatch(host, "(*\.|)taobaocdn.com") ||
            shExpMatch(host, "(*\.|)lxdns.com") ||
            shExpMatch(host, "(*\.|)sohu.com") ||
            shExpMatch(host, "(*\.|)ifeng.com") ||
            shExpMatch(host, "(*\.|)jysq.net") ||
            shExpMatch(host, "(*\.|)nipic.com") ||
            shExpMatch(host, "(*\.|)fastcdn.com") ||
            shExpMatch(host, "(*\.|)oeeee.com") ||
            shExpMatch(host, "(*\.|)mosso.com") ||
            shExpMatch(host, "(*\.|)pengyou.com") ||
            shExpMatch(host, "(*\.|)360buyimg.com") ||
            shExpMatch(host, "(*\.|)51buy.com") ||
            shExpMatch(host, "(*\.|)icson.com")
        ) {

        return 'DIRECT';
    }

    // alexa top 500 chinese sites
    if(
        shExpMatch(host, "(*\.|)baidu.com")  ||
            shExpMatch(host, "(*\.|)qq.com") ||
            shExpMatch(host, "(*\.|)taobao.com")||
            shExpMatch(host, "(*\.|)163.com") ||
            shExpMatch(host, "(*\.|)weibo.com")  ||
            shExpMatch(host, "(*\.|)sohu.com") ||
            shExpMatch(host, "(*\.|)youku.com")  ||
            shExpMatch(host, "(*\.|)soso.com") ||
            shExpMatch(host, "(*\.|)ifeng.com") ||
            shExpMatch(host, "(*\.|)tmall.com") ||
            shExpMatch(host, "(*\.|)hao123.com") ||
            shExpMatch(host, "(*\.|)tudou.com") ||
            shExpMatch(host, "(*\.|)360buy.com") ||
            shExpMatch(host, "(*\.|)chinaz.com") ||
            shExpMatch(host, "(*\.|)alipay.com") ||
            shExpMatch(host, "(*\.|)sogou.com") ||
            shExpMatch(host, "(*\.|)renren.com") ||
            shExpMatch(host, "(*\.|)cnzz.com") ||
            shExpMatch(host, "(*\.|)douban.com") ||
            shExpMatch(host, "(*\.|)pengyou.com") ||
            shExpMatch(host, "(*\.|)58.com") ||
            shExpMatch(host, "(*\.|)alibaba.com") ||
            shExpMatch(host, "(*\.|)56.com") ||
            shExpMatch(host, "(*\.|)xunlei.com") ||
            shExpMatch(host, "(*\.|)bing.com") ||
            shExpMatch(host, "(*\.|)iqiyi.com") ||
            shExpMatch(host, "(*\.|)csdn.net") ||
            shExpMatch(host, "(*\.|)soku.com") ||
            shExpMatch(host, "(*\.|)xinhuanet.com") ||
            shExpMatch(host, "(*\.|)ku6.com") ||
            shExpMatch(host, "(*\.|)aizhan.com") ||
            shExpMatch(host, "(*\.|)4399.com") ||
            shExpMatch(host, "(*\.|)yesky.com") ||
            shExpMatch(host, "(*\.|)soufun.com") ||
            shExpMatch(host, "(*\.|)youdao.com") ||
            shExpMatch(host, "(*\.|)china.com") ||
            shExpMatch(host, "(*\.|)hudong.com") ||
            shExpMatch(host, "(*\.|)ganji.com") ||
            shExpMatch(host, "(*\.|)kaixin001.com") ||
            shExpMatch(host, "(*\.|)paipai.com") ||
            shExpMatch(host, "(*\.|)live.com") ||
            shExpMatch(host, "(*\.|)alimama.com") ||
            shExpMatch(host, "(*\.|)mop.com") ||
            shExpMatch(host, "(*\.|)51.la") ||
            shExpMatch(host, "(*\.|)51job.com") ||
            shExpMatch(host, "(*\.|)dianping.com") ||
            shExpMatch(host, "(*\.|)126.com") ||
            shExpMatch(host, "(*\.|)admin5.com") ||
            shExpMatch(host, "(*\.|)it168.com") ||
            shExpMatch(host, "(*\.|)2345.com") ||
            shExpMatch(host, "(*\.|)huanqiu.com") ||
            shExpMatch(host, "(*\.|)arpg2.com") ||
            shExpMatch(host, "(*\.|)777wyx.com") ||
            shExpMatch(host, "(*\.|)chinanews.com") ||
            shExpMatch(host, "(*\.|)letv.com") ||
            shExpMatch(host, "(*\.|)jiayuan.com") ||
            shExpMatch(host, "(*\.|)39.net") ||
            shExpMatch(host, "(*\.|)twcczhu.com") ||
            shExpMatch(host, "(*\.|)cnblogs.com") ||
            shExpMatch(host, "(*\.|)microsoft.com") ||
            shExpMatch(host, "(*\.|)dangdang.com") ||
            shExpMatch(host, "(*\.|)pchome.net") ||
            shExpMatch(host, "(*\.|)pptv.com") ||
            shExpMatch(host, "(*\.|)vancl.com") ||
            shExpMatch(host, "(*\.|)zhaopin.com") ||
            shExpMatch(host, "(*\.|)apple.com") ||
            shExpMatch(host, "(*\.|)bitauto.com") ||
            shExpMatch(host, "(*\.|)etao.com") ||
            shExpMatch(host, "(*\.|)qunar.com") ||
            shExpMatch(host, "(*\.|)eastmoney.com") ||
            shExpMatch(host, "(*\.|)yihaodian.com") ||
            shExpMatch(host, "(*\.|)115.com") ||
            shExpMatch(host, "(*\.|)21cn.com") ||
            shExpMatch(host, "(*\.|)blog.163.com") ||
            shExpMatch(host, "(*\.|)hupu.com") ||
            shExpMatch(host, "(*\.|)duowan.com") ||
            shExpMatch(host, "(*\.|)52pk.net") ||
            shExpMatch(host, "(*\.|)baixing.com") ||
            shExpMatch(host, "(*\.|)iteye.com") ||
            shExpMatch(host, "(*\.|)verycd.com") ||
            shExpMatch(host, "(*\.|)suning.com") ||
            shExpMatch(host, "(*\.|)discuz.net") ||
            shExpMatch(host, "(*\.|)7k7k.com") ||
            shExpMatch(host, "(*\.|)mtime.com") ||
            shExpMatch(host, "(*\.|)msn.com") ||
            shExpMatch(host, "(*\.|)ccb.com") ||
            shExpMatch(host, "(*\.|)hc360.com") ||
            shExpMatch(host, "(*\.|)cmbchina.com") ||
            shExpMatch(host, "(*\.|)51.com") ||
            shExpMatch(host, "(*\.|)yoka.com") ||
            shExpMatch(host, "(*\.|)seowhy.com") ||
            shExpMatch(host, "(*\.|)chinabyte.com") ||
            shExpMatch(host, "(*\.|)qidian.com") ||
            shExpMatch(host, "(*\.|)ctrip.com") ||
            shExpMatch(host, "(*\.|)cnbeta.com") ||
            shExpMatch(host, "(*\.|)tom.com") ||
            shExpMatch(host, "(*\.|)tenpay.com") ||
            shExpMatch(host, "(*\.|)meituan.com") ||
            shExpMatch(host, "(*\.|)120ask.com") ||
            shExpMatch(host, "(*\.|)ebay.com") ||
            shExpMatch(host, "(*\.|)51cto.com") ||
            shExpMatch(host, "(*\.|)sdo.com") ||
            shExpMatch(host, "(*\.|)meilishuo.com") ||
            shExpMatch(host, "(*\.|)17173.com") ||
            shExpMatch(host, "(*\.|)xyxy.net") ||
            shExpMatch(host, "(*\.|)19lou.com") ||
            shExpMatch(host, "(*\.|)yiqifa.com") ||
            shExpMatch(host, "(*\.|)nuomi.com") ||
            shExpMatch(host, "(*\.|)eastday.com") ||
            shExpMatch(host, "(*\.|)onlinedown.net") ||
            shExpMatch(host, "(*\.|)oschina.net") ||
            shExpMatch(host, "(*\.|)zhubajie.com") ||
            shExpMatch(host, "(*\.|)amazon.com") ||
            shExpMatch(host, "(*\.|)babytree.com") ||
            shExpMatch(host, "(*\.|)kdnet.net") ||
            shExpMatch(host, "(*\.|)docin.com") ||
            shExpMatch(host, "(*\.|)qq937.com") ||
            shExpMatch(host, "(*\.|)tgbus.com") ||
            shExpMatch(host, "(*\.|)51buy.com") ||
            shExpMatch(host, "(*\.|)nipic.com") ||
            shExpMatch(host, "(*\.|)im286.com") ||
            shExpMatch(host, "(*\.|)baomihua.com") ||
            shExpMatch(host, "(*\.|)doubleclick.com") ||
            shExpMatch(host, "(*\.|)dh818.com") ||
            shExpMatch(host, "(*\.|)ads8.com") ||
            shExpMatch(host, "(*\.|)hiapk.com") ||
            shExpMatch(host, "(*\.|)ynet.com") ||
            shExpMatch(host, "(*\.|)sootoo.com") ||
            shExpMatch(host, "(*\.|)mogujie.com") ||
            shExpMatch(host, "(*\.|)gfan.com") ||
            shExpMatch(host, "(*\.|)ppstream.com") ||
            shExpMatch(host, "(*\.|)a135.net") ||
            shExpMatch(host, "(*\.|)ip138.com") ||
            shExpMatch(host, "(*\.|)zx915.com") ||
            shExpMatch(host, "(*\.|)lashou.com") ||
            shExpMatch(host, "(*\.|)crsky.com") ||
            shExpMatch(host, "(*\.|)iciba.com") ||
            shExpMatch(host, "(*\.|)uuzu.com") ||
            shExpMatch(host, "(*\.|)tuan800.com") ||
            shExpMatch(host, "(*\.|)haodf.com") ||
            shExpMatch(host, "(*\.|)youboy.com") ||
            shExpMatch(host, "(*\.|)ulink.cc") ||
            shExpMatch(host, "(*\.|)qiyou.com") ||
            shExpMatch(host, "(*\.|)88db.com") ||
            shExpMatch(host, "(*\.|)tao123.com") ||
            shExpMatch(host, "(*\.|)178.com") ||
            shExpMatch(host, "(*\.|)ci123.com") ||
            shExpMatch(host, "(*\.|)yolk7.com") ||
            shExpMatch(host, "(*\.|)tiexue.net") ||
            shExpMatch(host, "(*\.|)stockstar.com") ||
            shExpMatch(host, "(*\.|)xici.net") ||
            shExpMatch(host, "(*\.|)pcpop.com") ||
            shExpMatch(host, "(*\.|)linkedin.com") ||
            shExpMatch(host, "(*\.|)weiphone.com") ||
            shExpMatch(host, "(*\.|)doc88.com") ||
            shExpMatch(host, "(*\.|)adobe.com") ||
            shExpMatch(host, "(*\.|)shangdu.com") ||
            shExpMatch(host, "(*\.|)aili.com") ||
            shExpMatch(host, "(*\.|)anjuke.com") ||
            shExpMatch(host, "(*\.|)360doc.com") ||
            shExpMatch(host, "(*\.|)cnxad.com") ||
            shExpMatch(host, "(*\.|)west263.com") ||
            shExpMatch(host, "(*\.|)jiathis.com") ||
            shExpMatch(host, "(*\.|)gougou.com") ||
            shExpMatch(host, "(*\.|)whlongda.com") ||
            shExpMatch(host, "(*\.|)mnwan.com") ||
            shExpMatch(host, "(*\.|)onetad.com") ||
            shExpMatch(host, "(*\.|)duote.com") ||
            shExpMatch(host, "(*\.|)55bbs.com") ||
            shExpMatch(host, "(*\.|)iloveyouxi.com") ||
            shExpMatch(host, "(*\.|)gongchang.com") ||
            shExpMatch(host, "(*\.|)meishichina.com") ||
            shExpMatch(host, "(*\.|)qire123.com") ||
            shExpMatch(host, "(*\.|)55tuan.com") ||
            shExpMatch(host, "(*\.|)cocoren.com") ||
            shExpMatch(host, "(*\.|)xiaomi.com") ||
            shExpMatch(host, "(*\.|)phpwind.net") ||
            shExpMatch(host, "(*\.|)abchina.com") ||
            shExpMatch(host, "(*\.|)thethirdmedia.com")||
            shExpMatch(host, "(*\.|)coo8.com") ||
            shExpMatch(host, "(*\.|)aliexpress.com") ||
            shExpMatch(host, "(*\.|)onlylady.com") ||
            shExpMatch(host, "(*\.|)manzuo.com") ||
            shExpMatch(host, "(*\.|)elong.com") ||
            shExpMatch(host, "(*\.|)aibang.com") ||
            shExpMatch(host, "(*\.|)10010.com") ||
            shExpMatch(host, "(*\.|)3366.com") ||
            shExpMatch(host, "(*\.|)28tui.com") ||
            shExpMatch(host, "(*\.|)vipshop.com") ||
            shExpMatch(host, "(*\.|)1616.net") ||
            shExpMatch(host, "(*\.|)pp.cc") ||
            shExpMatch(host, "(*\.|)jumei.com") ||
            shExpMatch(host, "(*\.|)tui18.com") ||
            shExpMatch(host, "(*\.|)52tlbb.com") ||
            shExpMatch(host, "(*\.|)yinyuetai.com") ||
            shExpMatch(host, "(*\.|)eye.rs") ||
            shExpMatch(host, "(*\.|)baihe.com") ||
            shExpMatch(host, "(*\.|)iyaya.com") ||
            shExpMatch(host, "(*\.|)imanhua.com") ||
            shExpMatch(host, "(*\.|)lusongsong.com") ||
            shExpMatch(host, "(*\.|)taobaocdn.com") ||
            shExpMatch(host, "(*\.|)leho.com") ||
            shExpMatch(host, "(*\.|)315che.com") ||
            shExpMatch(host, "(*\.|)donews.com") ||
            shExpMatch(host, "(*\.|)cqnews.net") ||
            shExpMatch(host, "(*\.|)591hx.com") ||
            shExpMatch(host, "(*\.|)114la.com") ||
            shExpMatch(host, "(*\.|)gamersky.com") ||
            shExpMatch(host, "(*\.|)tangdou.com") ||
            shExpMatch(host, "(*\.|)91.com") ||
            shExpMatch(host, "(*\.|)uuu9.com") ||
            shExpMatch(host, "(*\.|)xinnet.com") ||
            shExpMatch(host, "(*\.|)dedecms.com") ||
            shExpMatch(host, "(*\.|)cnmo.com") ||
            shExpMatch(host, "(*\.|)51fanli.com") ||
            shExpMatch(host, "(*\.|)liebiao.com") ||
            shExpMatch(host, "(*\.|)yyets.com") ||
            shExpMatch(host, "(*\.|)lady8844.com") ||
            shExpMatch(host, "(*\.|)newsmth.net") ||
            shExpMatch(host, "(*\.|)ucjoy.com") ||
            shExpMatch(host, "(*\.|)duba.net") ||
            shExpMatch(host, "(*\.|)cnki.net") ||
            shExpMatch(host, "(*\.|)70e.com") ||
            shExpMatch(host, "(*\.|)funshion.com") ||
            shExpMatch(host, "(*\.|)qjy168.com") ||
            shExpMatch(host, "(*\.|)paypal.com") ||
            shExpMatch(host, "(*\.|)3dmgame.com") ||
            shExpMatch(host, "(*\.|)m18.com") ||
            shExpMatch(host, "(*\.|)caixin.com") ||
            shExpMatch(host, "(*\.|)linezing.com") ||
            shExpMatch(host, "(*\.|)53kf.com") ||
            shExpMatch(host, "(*\.|)makepolo.com") ||
            shExpMatch(host, "(*\.|)dospy.com") ||
            shExpMatch(host, "(*\.|)xiami.com") ||
            shExpMatch(host, "(*\.|)5173.com") ||
            shExpMatch(host, "(*\.|)vjia.com") ||
            shExpMatch(host, "(*\.|)hotsales.net") ||
            shExpMatch(host, "(*\.|)4738.com") ||
            shExpMatch(host, "(*\.|)mydrivers.com") ||
            shExpMatch(host, "(*\.|)alisoft.com") ||
            shExpMatch(host, "(*\.|)titan24.com") ||
            shExpMatch(host, "(*\.|)u17.com") ||
            shExpMatch(host, "(*\.|)jb51.net") ||
            shExpMatch(host, "(*\.|)diandian.com") ||
            shExpMatch(host, "(*\.|)dzwww.com") ||
            shExpMatch(host, "(*\.|)hichina.com") ||
            shExpMatch(host, "(*\.|)abang.com") ||
            shExpMatch(host, "(*\.|)qianlong.com") ||
            shExpMatch(host, "(*\.|)m1905.com") ||
            shExpMatch(host, "(*\.|)chinahr.com") ||
            shExpMatch(host, "(*\.|)zhaodao123.com") ||
            shExpMatch(host, "(*\.|)daqi.com") ||
            shExpMatch(host, "(*\.|)sourceforge.net") ||
            shExpMatch(host, "(*\.|)yaolan.com") ||
            shExpMatch(host, "(*\.|)5d6d.net") ||
            shExpMatch(host, "(*\.|)fobshanghai.com") ||
            shExpMatch(host, "(*\.|)q150.com") ||
            shExpMatch(host, "(*\.|)l99.com") ||
            shExpMatch(host, "(*\.|)ccidnet.com") ||
            shExpMatch(host, "(*\.|)aifang.com") ||
            shExpMatch(host, "(*\.|)aol.com") ||
            shExpMatch(host, "(*\.|)theplanet.com") ||
            shExpMatch(host, "(*\.|)chinaunix.net") ||
            shExpMatch(host, "(*\.|)hf365.com") ||
            shExpMatch(host, "(*\.|)ad1111.com") ||
            shExpMatch(host, "(*\.|)zhihu.com") ||
            shExpMatch(host, "(*\.|)blueidea.com") ||
            shExpMatch(host, "(*\.|)net114.com") ||
            shExpMatch(host, "(*\.|)07073.com") ||
            shExpMatch(host, "(*\.|)alivv.com") ||
            shExpMatch(host, "(*\.|)mplife.com") ||
            shExpMatch(host, "(*\.|)allyes.com") ||
            shExpMatch(host, "(*\.|)jqw.com") ||
            shExpMatch(host, "(*\.|)netease.com") ||
            shExpMatch(host, "(*\.|)1ting.com") ||
            shExpMatch(host, "(*\.|)yougou.com") ||
            shExpMatch(host, "(*\.|)dbank.com") ||
            shExpMatch(host, "(*\.|)made-in-china.com") ||
            shExpMatch(host, "(*\.|)36kr.com") ||
            shExpMatch(host, "(*\.|)wumii.com") ||
            shExpMatch(host, "(*\.|)zoosnet.net") ||
            shExpMatch(host, "(*\.|)xitek.com") ||
            shExpMatch(host, "(*\.|)ali213.net") ||
            shExpMatch(host, "(*\.|)exam8.com") ||
            shExpMatch(host, "(*\.|)jxedt.com") ||
            shExpMatch(host, "(*\.|)uniontoufang.com") ||
            shExpMatch(host, "(*\.|)zqgame.com") ||
            shExpMatch(host, "(*\.|)52kmh.com") ||
            shExpMatch(host, "(*\.|)yxlady.com") ||
            shExpMatch(host, "(*\.|)sznews.com") ||
            shExpMatch(host, "(*\.|)longhoo.net") ||
            shExpMatch(host, "(*\.|)game3737.com") ||
            shExpMatch(host, "(*\.|)51auto.com") ||
            shExpMatch(host, "(*\.|)booksky.org") ||
            shExpMatch(host, "(*\.|)iqilu.com") ||
            shExpMatch(host, "(*\.|)ddmap.com") ||
            shExpMatch(host, "(*\.|)cncn.com") ||
            shExpMatch(host, "(*\.|)ename.net") ||
            shExpMatch(host, "(*\.|)1778.com") ||
            shExpMatch(host, "(*\.|)blogchina.com") ||
            shExpMatch(host, "(*\.|)778669.com") ||
            shExpMatch(host, "(*\.|)dayoo.com") ||
            shExpMatch(host, "(*\.|)ct10000.com") ||
            shExpMatch(host, "(*\.|)zhibo8.cc") ||
            shExpMatch(host, "(*\.|)qingdaonews.com") ||
            shExpMatch(host, "(*\.|)zongheng.com") ||
            shExpMatch(host, "(*\.|)1o26.com") ||
            shExpMatch(host, "(*\.|)oeeee.com") ||
            shExpMatch(host, "(*\.|)tiancity.com") ||
            shExpMatch(host, "(*\.|)jinti.com") ||
            shExpMatch(host, "(*\.|)si.kz") ||
            shExpMatch(host, "(*\.|)tuniu.com") ||
            shExpMatch(host, "(*\.|)xiu.com") ||
            shExpMatch(host, "(*\.|)265.com") ||
            shExpMatch(host, "(*\.|)gamestlbb.com") ||
            shExpMatch(host, "(*\.|)2hua.com") ||
            shExpMatch(host, "(*\.|)moonbasa.com") ||
            shExpMatch(host, "(*\.|)sf-express.com") ||
            shExpMatch(host, "(*\.|)qiushibaike.com") ||
            shExpMatch(host, "(*\.|)ztgame.com") ||
            shExpMatch(host, "(*\.|)yupoo.com") ||
            shExpMatch(host, "(*\.|)kimiss.com") ||
            shExpMatch(host, "(*\.|)cnhubei.com") ||
            shExpMatch(host, "(*\.|)pingan.com") ||
            shExpMatch(host, "(*\.|)lafaso.com") ||
            shExpMatch(host, "(*\.|)rakuten.co.jp") ||
            shExpMatch(host, "(*\.|)zhenai.com") ||
            shExpMatch(host, "(*\.|)tiao8.info") ||
            shExpMatch(host, "(*\.|)7c.com") ||
            shExpMatch(host, "(*\.|)tianji.com") ||
            shExpMatch(host, "(*\.|)kugou.com") ||
            shExpMatch(host, "(*\.|)house365.com") ||
            shExpMatch(host, "(*\.|)flickr.com") ||
            shExpMatch(host, "(*\.|)xiazaiba.com") ||
            shExpMatch(host, "(*\.|)aipai.com") ||
            shExpMatch(host, "(*\.|)sodu.org") ||
            shExpMatch(host, "(*\.|)bankcomm.com") ||
            shExpMatch(host, "(*\.|)lietou.com") ||
            shExpMatch(host, "(*\.|)toocle.com") ||
            shExpMatch(host, "(*\.|)fengniao.com") ||
            shExpMatch(host, "(*\.|)99bill.com") ||
            shExpMatch(host, "(*\.|)bendibao.com") ||
            shExpMatch(host, "(*\.|)mapbar.com") ||
            shExpMatch(host, "(*\.|)nowec.com") ||
            shExpMatch(host, "(*\.|)yingjiesheng.com")||
            shExpMatch(host, "(*\.|)comsenz.com") ||
            shExpMatch(host, "(*\.|)meilele.com") ||
            shExpMatch(host, "(*\.|)otwan.com") ||
            shExpMatch(host, "(*\.|)61.com") ||
            shExpMatch(host, "(*\.|)meizu.com") ||
            shExpMatch(host, "(*\.|)readnovel.com") ||
            shExpMatch(host, "(*\.|)fenzhi.com") ||
            shExpMatch(host, "(*\.|)up2c.com") ||
            shExpMatch(host, "(*\.|)500wan.com") ||
            shExpMatch(host, "(*\.|)fx120.net") ||
            shExpMatch(host, "(*\.|)ftuan.com") ||
            shExpMatch(host, "(*\.|)17u.com") ||
            shExpMatch(host, "(*\.|)lehecai.com") ||
            shExpMatch(host, "(*\.|)28.com") ||
            shExpMatch(host, "(*\.|)bilibili.tv") ||
            shExpMatch(host, "(*\.|)huaban.com") ||
            shExpMatch(host, "(*\.|)szhome.com") ||
            shExpMatch(host, "(*\.|)miercn.com") ||
            shExpMatch(host, "(*\.|)fblife.com") ||
            shExpMatch(host, "(*\.|)chinaw3.com") ||
            shExpMatch(host, "(*\.|)smzdm.com") ||
            shExpMatch(host, "(*\.|)b2b168.com") ||
            shExpMatch(host, "(*\.|)265g.com") ||
            shExpMatch(host, "(*\.|)anzhi.com") ||
            shExpMatch(host, "(*\.|)chuangelm.com") ||
            shExpMatch(host, "(*\.|)php100.com") ||
            shExpMatch(host, "(*\.|)100ye.com") ||
            shExpMatch(host, "(*\.|)hefei.cc") ||
            shExpMatch(host, "(*\.|)mumayi.com") ||
            shExpMatch(host, "(*\.|)sttlbb.com") ||
            shExpMatch(host, "(*\.|)mangocity.com") ||
            shExpMatch(host, "(*\.|)fantong.com")
        ) {
        return 'DIRECT';
    }

    // if none of above cases, it is always safe to use the proxy
    return proxy;
}


/*
 MIT License
 Copyright (C) 2012 n0gfwall0@gmail.com

 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the "Software"),
 to deal in the Software without restriction, including without limitation
 the rights to use, copy, modify, merge, publish, distribute, sublicense,
 and/or sell copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 IN THE SOFTWARE.

 */