"""来源白名单与发现层数据源。"""

from __future__ import annotations

from urllib.parse import urlparse

# 内容层可信来源（域名 → 名称）
WHITELIST = {
    "36kr.com": "36氪",
    "huxiu.com": "虎嗅",
    "tmtpost.com": "钛媒体",
    "ifanr.com": "爱范儿",
    "geekpark.net": "极客公园",
    "jiemian.com": "界面新闻",
    "yicai.com": "第一财经",
    "thepaper.cn": "澎湃新闻",
    "sina.com.cn": "新浪科技",
    "aliyun.com": "阿里云官方",
    "qwen.ai": "通义官方",
    "qbitai.com": "量子位",
    "sspai.com": "少数派",
    "oschina.net": "开源中国",
    "cnbeta.com.tw": "cnBeta",
    "infoq.cn": "InfoQ中文",
    "leiphone.com": "雷锋网",
    "aiera.com.cn": "新智元",
}

# 发现层数据源：已验证可稳定抓取的官方 RSS（来源名称 → 订阅地址）
RSS_FEEDS = {
    "钛媒体": "https://www.tmtpost.com/rss",
    "爱范儿": "https://www.ifanr.com/feed",
    "极客公园": "https://www.geekpark.net/rss",
    "量子位": "https://www.qbitai.com/feed",
    "少数派": "https://sspai.com/feed",
    "开源中国": "https://www.oschina.net/news/rss",
    "cnBeta": "https://www.cnbeta.com.tw/backend.php",
    "InfoQ中文": "https://www.infoq.cn/feed",
    "雷锋网": "https://www.leiphone.com/feed",
    "新智元": "https://www.aiera.com.cn/feed",
}

# 待处理：36氪 feed 有反爬（返回 HTML），虎嗅连接超时，接入后补充到 RSS_FEEDS。


def _domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def is_whitelisted(url: str) -> bool:
    domain = _domain(url)
    return any(domain == d or domain.endswith("." + d) for d in WHITELIST)


def source_name(url: str) -> str:
    domain = _domain(url)
    for d, name in WHITELIST.items():
        if domain == d or domain.endswith("." + d):
            return name
    return domain or "未知来源"