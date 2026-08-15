"""发现层工具：在可信媒体 RSS 与列表页中按关键词检索候选文章（国内可达、无代理）。"""

from __future__ import annotations

import concurrent.futures
import html
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..sources import LIST_PAGES, RSS_FEEDS

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
            "在可信垂直媒体（钛媒体、爱范儿、极客公园、量子位、少数派、开源中国、cnBeta、InfoQ中文、雷锋网、新智元、IT之家、Solidot 的 RSS，"
            "以及第一财经、界面新闻、21财经的文章列表）的最新文章中按关键词检索候选报道，返回标题、来源、链接与日期。"
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


def _fetch_text(url: str) -> str:
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


_AGGREGATE_RE = re.compile(r"早报|晚报|晨报|午报|周记|周报|月报|早知道|盘点|汇总|集锦|速览|要闻|大事记|数读")


def _score_title(
    title: str,
    desc: str,
    orig_terms: list[str],
    expanded_terms: list[str],
    weak_orig: set[str] | frozenset[str] = frozenset(),
) -> tuple[float, list[str]]:
    """实体词原标题命中 +3、正文/摘要命中 +2；领域弱词（融资/估值/AI…）降为 +1.5/+1.0；
    2-gram 兜底 +0.5。聚合/盘点类标题（早报/周记/早知道…）即使命中分数封顶 1.5，避免霸榜。"""
    hay_title = title.lower()
    hay_all = (title + " " + desc).lower()
    score = 0.0
    matched: list[str] = []
    for term in orig_terms:
        tl = term.lower()
        weak = term in weak_orig
        if tl in hay_title:
            score += 1.5 if weak else 3.0
            if not weak:
                matched.append(term)
        elif tl in hay_all:
            score += 1.0 if weak else 2.0
            if not weak:
                matched.append(term)
    gram_score = 0.0
    for term in expanded_terms:
        if term.lower() in hay_all:
            gram_score += 0.5
    score += min(gram_score, 1.0)  # 2-gram 兜底总贡献封顶 1.0，只做召回、不主导排序
    if _AGGREGATE_RE.search(title):
        score = min(score, 1.0)  # 聚合文章即使命中实体也低于“真相关”阈值（含财经源加成后仍 <2.0）
    # 2-gram/弱词兜底只做召回：没有原词命中时分数封顶 1.0，避免泛匹配排到前面
    if not matched and score > 1.0:
        score = 1.0
    return score, matched


def _match_items(
    xml_text: str,
    orig_terms: list[str],
    expanded_terms: list[str],
    limit: int,
    weak_orig: set[str] = frozenset(),
) -> list[dict]:
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
        score, matched = _score_title(title, desc, orig_terms, expanded_terms, weak_orig)
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


_DATE_RE = re.compile(r"(\d{4})年?[-./年](\d{1,2})月?[-./月](\d{1,2})日?")
_CATEGORY_TAGS = re.compile(r"·\s*(文章|头条|快讯|独家|深度|专题)\s*")


def _norm_date(text: str) -> str:
    m = _DATE_RE.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _match_list_page(
    html_text: str,
    base_url: str,
    cfg: dict,
    orig_terms: list[str],
    expanded_terms: list[str],
    limit: int,
    weak_orig: set[str] = frozenset(),
) -> list[dict]:
    """从无 RSS 站点的列表页提取文章链接，按标题关键词匹配（配置见 sources.LIST_PAGES）。"""
    soup = BeautifulSoup(html_text, "html.parser")
    link_subs = cfg.get("link_match") or []
    title_sels = cfg.get("title_selectors") or []
    date_sels = cfg.get("date_selectors") or []
    drop_date_spans = cfg.get("drop_date_spans", False)

    seen: set[str] = set()
    items: list[dict] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not any(sub in href for sub in link_subs):
            continue
        if not href.startswith(("http://", "https://")):
            href = urljoin(base_url, href)
        if href in seen:
            continue

        title = ""
        title_attr = cfg.get("title_attr")
        if title_attr:
            title = (a.get(title_attr) or "").strip()
            if len(title) < 4:
                title = ""
        if not title:
            for sel in title_sels:
                node = a.select_one(sel)
                text = node.get_text(" ", strip=True) if node else ""
                if len(text) >= 4:
                    title = text
                    break
        if not title:
            clone = BeautifulSoup(str(a), "html.parser").a or a
            if drop_date_spans:
                for span in clone.find_all("span"):
                    if _DATE_RE.match(span.get_text(" ", strip=True) or ""):
                        span.decompose()
            title = _CATEGORY_TAGS.sub("", clone.get_text(" ", strip=True))
            title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 4:
            title = (a.get("aria-label") or "").strip() or (a.get("title") or "").strip()
        if len(title) < 4:
            continue
        seen.add(href)

        date = ""
        for sel in date_sels:
            node = a.select_one(sel)
            if node:
                date = _norm_date(_CATEGORY_TAGS.sub("", node.get_text(" ", strip=True)))
                if date:
                    break

        score, matched = _score_title(title, "", orig_terms, expanded_terms, weak_orig)
        if score <= 0:
            continue
        items.append(
            {
                "title": title,
                "url": href,
                "date": date,
                "snippet": "",
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


# 中英/数字混合边界（如 白敬亭GOODBAI → 白敬亭 + GOODBAI）
_CJK_LATIN_SPLIT = re.compile(
    r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])"
)

# 拆出的弱词：2 字中文品类词 + 常见英文泛后缀（只做 +0.5 召回，避免泛匹配虚高）
_WEAK_SUBTERMS = {
    "app", "api", "pro", "plus", "max", "mini", "web", "pc", "os",
    "ai", "vr", "ar", "iq", "tv",
}


def _is_weak_subterm(sub: str) -> bool:
    if re.fullmatch(r"[\u4e00-\u9fff]{2}", sub):
        return True
    return sub.lower() in _WEAK_SUBTERMS


def _extract_terms(query: str) -> tuple[list[str], list[str]]:
    """从课题/关键词中提取实体词，返回（强实体词, 弱词）。

    强词：完整实体/产品名（命中 +3）；弱词：从混合词拆出的品类/泛后缀（命中 +0.5）。
    示例：豆包大模型 → 豆包/大模型（强）；QQ音乐 → QQ（强）+ 音乐（弱）。
    """
    strong: list[str] = []
    weak: list[str] = []

    def add_strong(t: str) -> None:
        if len(t) >= 2 and t not in GENERIC_TERMS and t not in strong:
            strong.append(t)

    def add_weak(t: str) -> None:
        if len(t) >= 2 and t not in GENERIC_TERMS and t not in weak and t not in strong:
            weak.append(t)

    for part in _SPLIT_RE.split(query):
        p = part
        for phrase in _DROP_PHRASES:
            p = p.replace(phrase, "")
        p = re.sub(r"\d{4}年?$", "", p)  # 去掉尾部年份（宁德时代2026年 → 宁德时代），减少泛 2-gram 噪音
        p = p.strip()
        if len(p) < 2 or p in GENERIC_TERMS:
            continue
        add_strong(p)
        # 公司前缀 + 产品名 → 补一个去掉前缀的实体（如 阿里通义千问 → 通义千问）
        for prefix in _COMPANY_PREFIXES:
            if p.startswith(prefix) and len(p) > len(prefix):
                rest = p[len(prefix):]
                if len(rest) >= 2 and rest not in GENERIC_TERMS and rest not in strong:
                    strong.append(rest)
                break
        # 中英/数字混合边界拆词（如 白敬亭GOODBAI → 白敬亭 + GOODBAI）
        for sub in _CJK_LATIN_SPLIT.split(p):
            if len(sub) < 2 or sub == p or sub in GENERIC_TERMS or sub.isdigit():
                continue
            if _is_weak_subterm(sub):
                add_weak(sub)
            else:
                add_strong(sub)
        # 已知领域词切分（如 豆包大模型 → 豆包 + 大模型，提高召回）
        for known in _KNOWN_SUBTERMS:
            if known != p and known in p:
                add_strong(known)
    return strong, weak


# 项目根目录（crawler/tools/search.py 向上三级）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 内置兜底词表：config/domain_terms.json 缺失或损坏时使用（完整词表以 JSON 为准）
_DEFAULT_DOMAIN_TERMS: dict[str, dict[str, int]] = {
    "科技": {
        "大模型": 2, "人工智能": 2, "芯片": 2, "算力": 2, "GPU": 2,
        "自动驾驶": 2, "机器人": 2, "量子": 2, "AI": 2, "开源": 1,
    },
    "金融": {
        "美联储": 2, "央行": 2, "降息": 2, "融资": 2, "估值": 2,
        "IPO": 2, "财报": 2, "A股": 2, "股价": 2, "银行": 1,
    },
}


def _load_domain_terms() -> dict[str, dict[str, int]]:
    """加载 config/domain_terms.json（科技/金融 → 子类 → 词:权重），压平为 {领域: {词: 权重}}。"""
    path = _PROJECT_ROOT / "config" / "domain_terms.json"
    try:
        with io.open(path, encoding="utf-8") as f:
            raw = json.load(f)
        flat: dict[str, dict[str, int]] = {}
        for domain, subclasses in raw.items():
            terms: dict[str, int] = {}
            for items in subclasses.values():
                for term, weight in items.items():
                    terms[term] = int(weight)
            flat[domain] = terms
        return flat
    except Exception:
        return {k: dict(v) for k, v in _DEFAULT_DOMAIN_TERMS.items()}


# 领域词表（词 → 权重：2 强 / 1 弱），加载自 config/domain_terms.json
DOMAIN_TERMS: dict[str, dict[str, int]] = _load_domain_terms()

# 专业财经源：金融领域选题时加分
FINANCE_SOURCES = {"第一财经", "界面新闻", "21财经"}

# 强中文领域词（权重≥2）：用于中文复合词内的已知词切分（如 豆包大模型 → 豆包 + 大模型）；弱词只参与领域判定
_KNOWN_SUBTERMS = {
    t
    for terms in DOMAIN_TERMS.values()
    for t, w in terms.items()
    if w >= 2 and re.fullmatch(r"[\u4e00-\u9fff]{2,}", t)
}


def domain_of(query: str) -> str:
    """按领域词表加权判断课题所属领域：科技 / 金融 / 综合 / 其他（强词 +2，弱词 +1）。"""
    text = query.lower()
    tech = sum(w for t, w in DOMAIN_TERMS.get("科技", {}).items() if t.lower() in text)
    fin = sum(w for t, w in DOMAIN_TERMS.get("金融", {}).items() if t.lower() in text)
    if tech and fin:
        return "综合"
    if tech:
        return "科技"
    if fin:
        return "金融"
    return "其他"


def _parse_date(date_str: str) -> datetime | None:
    """解析 RSS pubDate 或 YYYY-MM-DD 为 naive datetime，失败返回 None。"""
    if not date_str:
        return None
    s = date_str.strip()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    try:
        dt = parsedate_to_datetime(s)
        return dt.replace(tzinfo=None)
    except Exception:
        return None


def _date_weight(date_str: str) -> float:
    """日期衰减：7 天内 ×1.2，30 天内 ×1.0，更早 ×0.5；无日期不惩罚。"""
    dt = _parse_date(date_str)
    if dt is None:
        return 1.0
    days = (datetime.now() - dt).days
    if days <= 7:
        return 1.2
    if days <= 30:
        return 1.0
    return 0.5


def search_candidates(query: str, count: int = 5) -> tuple[list[dict], list[str]]:
    """在可信来源（白名单 RSS + 列表页）中按关键词检索，返回（按相关度排序的候选列表, 不可用来源列表）。

    每个候选含：title/url/date/snippet/score/source/matched。
    通用词（市场/竞争/分析…）不参与计分，只有具体产品/实体名命中才算相关。
    """
    orig_terms, weak_terms = _extract_terms(query)
    if not orig_terms:
        return [], []
    # 领域通用词（融资/估值/大模型…）在课题已有具体实体词时降级为弱词，避免泛匹配霸榜；
    # 纯领域词课题（如“美联储降息”）保持强词权重，否则将无词可搜。
    domain_words = {t.lower() for terms in DOMAIN_TERMS.values() for t in terms}
    has_core = any(t.lower() not in domain_words for t in orig_terms)
    weak_orig = {t for t in orig_terms if t.lower() in domain_words} if has_core else set()
    expanded_terms = [t for t in _expand_terms(orig_terms) if t not in orig_terms]
    for t in weak_terms:
        if t not in expanded_terms:
            expanded_terms.append(t)
    limit = max(1, min(int(count), 10))

    jobs: list[tuple[str, str, str, dict | None]] = []  # (来源名, url, 类型, 配置)
    for name, url in RSS_FEEDS.items():
        jobs.append((name, url, "rss", None))
    for name, cfg in LIST_PAGES.items():
        for page in cfg.get("pages", []):
            jobs.append((name, page, "list", cfg))

    results: list[dict] = []
    failed: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(jobs))) as pool:
        futures = {
            pool.submit(_fetch_text, url): (name, url, kind, cfg)
            for name, url, kind, cfg in jobs
        }
        for fut in concurrent.futures.as_completed(futures):
            name, url, kind, cfg = futures[fut]
            try:
                text = fut.result()
                if kind == "rss":
                    items = _match_items(text, orig_terms, expanded_terms, limit, weak_orig)
                else:
                    items = _match_list_page(text, url, cfg, orig_terms, expanded_terms, limit, weak_orig)
                for item in items:
                    item["source"] = name
                    results.append(item)
            except Exception:
                failed.append(name)

    # 按 URL 去重（同一文章可能出现在多个页面/来源）
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for item in results:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        deduped.append(item)
    results = deduped
    failed = list(dict.fromkeys(failed))
    domain = domain_of(query)
    for item in results:
        if domain == "金融" and item.get("source") in FINANCE_SOURCES:
            item["score"] = round(item["score"] + 0.5, 2)
        item["score"] = round(item["score"] * _date_weight(item["date"]), 2)
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
