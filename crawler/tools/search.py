"""发现层工具：在可信媒体官方 RSS 中按关键词检索候选文章（国内可达、无代理）。"""

from __future__ import annotations

import concurrent.futures
import html
import re
import xml.etree.ElementTree as ET

import requests

from ..sources import RSS_FEEDS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 12

SPEC = {
    "type": "function",
    "function": {
        "name": "search_news",
        "description": (
            "在可信科技媒体（钛媒体/爱范儿/极客公园/量子位/少数派/开源中国/cnBeta/InfoQ中文/雷锋网/新智元 等）的"
            "最新文章中按关键词检索候选报道，返回标题、来源、链接与日期。"
            "适合用来发现近期相关报道。如果某个关键词搜不到结果，请换更宽泛的关键词（如：通义千问、Qwen、阿里云）重试。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，例如：百炼 或 通义千问"},
                "count": {
                    "type": "integer",
                    "description": "每个来源最多返回条数，默认 5",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


def _fetch_feed(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    enc = resp.apparent_encoding or "utf-8"
    return resp.content.decode(enc, errors="replace")


def _expand_terms(terms: list[str]) -> list[str]:
    """宽松匹配兜底：对 4 字以上的词组补充 2-gram，提高召回。"""
    expanded = list(terms)
    for term in terms:
        if len(term) >= 4:
            expanded.extend(term[i : i + 2] for i in range(len(term) - 1))
    return expanded


def _match_items(xml_text: str, orig_terms: list[str], expanded_terms: list[str], limit: int) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        title = html.unescape(item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        desc = html.unescape(
            re.sub(r"<[^>]+>", "", item.findtext("description") or "")
        ).strip()
        if not title or not link:
            continue
        hay_title = title.lower()
        hay_all = (title + " " + desc).lower()
        score = 0.0
        matched: list[str] = []
        for term in orig_terms:
            tl = term.lower()
            if tl in hay_title:
                score += 3.0
                matched.append(term)
            elif tl in hay_all:
                score += 2.0
                matched.append(term)
        for term in expanded_terms:
            if term.lower() in hay_all:
                score += 0.5
        if score <= 0:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "date": pub_date,
                "snippet": desc[:120],
                "score": round(score, 2),
                "matched": matched,
            }
        )
    items.sort(key=lambda x: (x["score"], x["date"]), reverse=True)
    return items[:limit]


GENERIC_TERMS = {
    "市场", "竞争", "分析", "对比", "态势", "竞争态势", "最新", "动态", "情况",
    "现状", "趋势", "前景", "排名", "市场份额", "用户", "产品", "公司", "行业",
    "相关", "新闻", "报道", "文章", "评价", "口碑", "如何", "为什么", "怎么样",
    "区别", "差异", "哪个", "谁", "好", "份额",
}


_SPLIT_RE = re.compile(r"[\s,，、;；/]+|与|和|及|旗下|的|vs\.?|VS\.?")
_DROP_PHRASES = [
    "分析", "关于", "针对", "进行", "了解", "关注", "对比",
    "竞争态势", "态势", "现状", "情况", "前景", "趋势", "排名", "竞争",
    "最新", "动态", "市场", "用户", "产品", "公司", "行业", "文章", "新闻",
]

# 常见母公司名：单独命中时不足以证明话题相关（例如“腾讯”常出现在任何商业新闻里）
BROAD_COMPANIES = {
    "腾讯", "字节", "字节跳动", "阿里", "阿里巴巴", "阿里云", "百度", "华为",
    "小米", "美团", "京东", "网易", "360", "快手", "哔哩哔哩", "B站",
}
_COMPANY_PREFIXES = [
    "字节跳动", "阿里巴巴", "阿里云", "腾讯", "阿里", "字节",
    "百度", "华为", "小米", "美团", "京东", "网易",
]


def _extract_terms(query: str) -> list[str]:
    """从课题/关键词中提取候选实体词：按连接词切分，剔除通用修饰语。"""
    terms: list[str] = []
    for part in _SPLIT_RE.split(query):
        p = part
        for phrase in _DROP_PHRASES:
            p = p.replace(phrase, "")
        p = p.strip()
        if len(p) < 2 or p in GENERIC_TERMS:
            continue
        if p not in terms:
            terms.append(p)
        # 公司前缀 + 产品名 → 补一个去掉前缀的实体（如 阿里通义千问 → 通义千问）
        for prefix in _COMPANY_PREFIXES:
            if p.startswith(prefix) and len(p) > len(prefix):
                rest = p[len(prefix):]
                if len(rest) >= 2 and rest not in GENERIC_TERMS and rest not in terms:
                    terms.append(rest)
                break
    return terms


def search_candidates(query: str, count: int = 5) -> tuple[list[dict], list[str]]:
    """在白名单 RSS 中按关键词检索，返回（按相关度排序的候选列表, 不可用来源列表）。

    每个候选含：title/url/date/snippet/score/source/matched。
    通用词（市场/竞争/分析…）不参与计分，只有具体产品/实体名命中才算相关。
    """
    orig_terms = _extract_terms(query)
    if not orig_terms:
        return [], []
    expanded_terms = [t for t in _expand_terms(orig_terms) if t not in orig_terms]
    limit = max(1, min(int(count), 10))

    results: list[dict] = []
    failed: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as pool:
        futures = {
            pool.submit(_fetch_feed, url): name for name, url in RSS_FEEDS.items()
        }
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                for item in _match_items(fut.result(), orig_terms, expanded_terms, limit):
                    item["source"] = name
                    results.append(item)
            except Exception:
                failed.append(name)

    results.sort(key=lambda x: (x["score"], x["date"]), reverse=True)
    return results, failed


def run(query: str, count: int = 5) -> str:
    if not query or not query.strip():
        return "关键词为空，请提供有效关键词。"
    results, failed = search_candidates(query, count)
    if not results:
        note = f"（{len(failed)} 个来源暂时不可用：{', '.join(failed)}）" if failed else ""
        return f"在可信媒体中没有搜到与“{query}”相关的文章，请换关键词试试。{note}"
    lines = []
    for i, item in enumerate(results[:20], start=1):
        lines.append(
            f"{i}. {item['title']}（来源：{item['source']}，相关度 {item['score']}）\n"
            f"   链接：{item['url']}\n   日期：{item['date']}"
        )
    note = f"\n（另有 {len(failed)} 个来源暂时不可用：{', '.join(failed)}）" if failed else ""
    return f"找到 {len(results)} 条相关候选：\n" + "\n".join(lines) + note