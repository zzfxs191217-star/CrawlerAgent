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
    # 方向 C 扩展（2026-08-15 实测，正文抽取干净）：
    "ithome.com": "IT之家",
    "gcores.com": "机核",
    "solidot.org": "Solidot",
    "ylzbl.com": "娱乐资本论",
    "brandstar.com.cn": "品牌星球",
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
    "IT之家": "https://www.ithome.com/rss/",
    "机核": "https://www.gcores.com/rss",
    "Solidot": "https://www.solidot.org/index.rss",
}

# 无官方 RSS 站点的“列表页发现源”（名称 → 配置）：发现层抓取这些页面，
# 从文章链接中提取标题参与关键词检索（2026-08-15 实测，抽取规则见 D-015）。
LIST_PAGES: dict[str, dict] = {
    "娱乐资本论": {
        "pages": ["https://www.ylzbl.com/"],
        "link_match": ["/article/"],
        "title_selectors": ["h2"],
        "date_selectors": ["span.featured-slide-date", "div.post-card-meta"],
        "drop_date_spans": False,
    },
    "品牌星球": {
        "pages": ["https://www.brandstar.com.cn/"],
        "link_match": ["/news/", "/in-depth/", "/brand/"],
        "title_selectors": ["h2", "h4", ".hf-title"],
        "date_selectors": ["span.nd", ".m"],
        "drop_date_spans": True,
    },
}


# 待处理：36氪 feed 有反爬（返回 HTML），虎嗅连接超时，接入后补充到 RSS_FEEDS。
# 方向 C 已实测不接入（避免重复踩坑）：机器之心 rss 返回付费服务页、亿欧返回 202（反爬拦截）、
# DoNews/品玩 /rss 404、晚点 SSL 错误、三声域名已废弃；娱乐资本论/品牌星球无官方 RSS，
# 仅入内容层白名单，发现层列表页抓取作为方向 C 后续步骤。


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