"""网页抓取工具：根据网址返回页面标题与正文文本。"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15
DEFAULT_MAX_CHARS = 6000

SPEC = {
    "type": "function",
    "function": {
        "name": "fetch_web_page",
        "description": "抓取指定网址的网页，返回页面标题和正文文本（正文最多截断到 max_chars 字符）。",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页完整地址，例如 https://www.baidu.com",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "返回正文的最大字符数，默认 6000",
                    "default": 6000,
                },
            },
            "required": ["url"],
        },
    },
}


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


CONTENT_SELECTORS = [
    "article",
    ".article-content", ".article_content", "#article-content",
    ".post-content", ".entry-content", ".rich_media_content",
    ".article-detail", ".article", ".content", "#content", "main",
]


def _extract_content(soup) -> "BeautifulSoup":
    """优先返回文章正文容器，找不到时回退整个页面。"""
    best, best_len = None, 0
    for selector in CONTENT_SELECTORS:
        for node in soup.select(selector):
            length = len(node.get_text("", strip=True))
            if length > best_len:
                best, best_len = node, length
    if best is not None and best_len >= 200:
        return best
    return soup


def _clean_lines(soup: BeautifulSoup) -> list[str]:
    lines = [
        ln.strip() for ln in soup.get_text("\n", strip=True).splitlines() if ln.strip()
    ]
    lines = [re.sub(r"<[^>]+>", "", ln).strip() for ln in lines]
    return [ln for ln in lines if ln]


def run(url: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    url = _normalize_url(url)
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    main_node = _extract_content(soup)
    text = "\n".join(_clean_lines(main_node))
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "……（已截断）"
    return f"标题：{title}\n正文（{len(text)} 字符）：\n{text}"