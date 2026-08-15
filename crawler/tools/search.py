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


def run(query: str, count: int = 5) -> str:
    orig_terms = [t for t in re.split(r"[\s,，、;；]+", query) if t]
    if not orig_terms:
        return "关键词为空，请提供有效关键词。"
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

    if not results:
        note = f"（{len(failed)} 个来源暂时不可用：{', '.join(failed)}）" if failed else ""
        return f"在可信媒体中没有搜到与“{query}”相关的文章，请换关键词试试。{note}"

    results.sort(key=lambda x: (x["score"], x["date"]), reverse=True)
    lines = []
    for i, item in enumerate(results[:20], start=1):
        lines.append(
            f"{i}. {item['title']}（来源：{item['source']}，相关度 {item['score']}）\n"
            f"   链接：{item['url']}\n   日期：{item['date']}"
        )
    note = f"\n（另有 {len(failed)} 个来源暂时不可用：{', '.join(failed)}）" if failed else ""
    return f"找到 {len(results)} 条相关候选：\n" + "\n".join(lines) + note