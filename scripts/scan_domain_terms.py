"""数据驱动领域词候选生成：抓科技/金融源近 N 篇，jieba 分词 + 词频统计 + 领域判别力评分。

用法：
    uv run python scripts/scan_domain_terms.py --per-source 80 --top 120
    uv run python scripts/scan_domain_terms.py --per-source 80 --top 120 --out docs/domain_terms_candidates.md

原理：把现有源分为“科技组”（白名单 RSS 标题）与“金融组”（财经列表页标题），同口径分别统计词频；
用 log 比率 log((t+1)/(f+1)) 衡量领域判别力，明显偏向某组且总频次够高的词 → 候选领域词。
产出 Markdown 候选清单，人工审核后并入 config/domain_terms.json（不自动入库，避免噪声）。
"""

from __future__ import annotations

import argparse
import io
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import jieba
import requests
from bs4 import BeautifulSoup

# 确保能以“项目根”导入 crawler 包（脚本位于 scripts/ 目录）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawler.sources import LIST_PAGES, RSS_FEEDS
from crawler.tools.search import BROAD_COMPANIES, DOMAIN_TERMS, GENERIC_TERMS

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 12

# 停用词：中文虚词 + 新闻套话 + 通用词 + 母公司词（母公司词判别力低，先剔除）
_STOPWORDS = (
    set("的了是在我有和就不人都一个上也很到说要去你会着没有好看自己这那等及与而或但并被把让向从为对于已经将正在".strip())
    | {
        "表示", "记者", "报道", "来源", "图片", "视频", "编辑", "作者", "点击", "阅读",
        "更多", "相关", "进行", "我们", "他们", "大家", "今年", "去年", "目前", "近日",
        "最新", "今日", "昨日", "明天", "今天", "发布", "推出", "上线", "宣布", "认为",
        "指出", "强调", "显示", "透露", "采访", "全球", "中国", "国内", "国际", "美国",
        "日本", "韩国", "欧洲", "上海", "北京", "深圳", "广州", "香港", "其中", "以及",
        "已经", "上半年", "下半年", "一季度", "二季度", "三季度", "四季度", "月份",
        "可以", "没有", "成为", "出现", "开始", "带来", "实现", "提升", "增长", "下降",
        "同比", "环比", "数量", "金额", "规模", "水平", "方面", "领域", "方向", "问题",
    }
    | GENERIC_TERMS
    | BROAD_COMPANIES
)


def fetch_rss_items(url: str, limit: int) -> list[str]:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    enc = resp.apparent_encoding or "utf-8"
    root = ET.fromstring(resp.content.decode(enc, errors="replace"))
    texts: list[str] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        # 与金融列表页保持同口径：只用标题统计，避免“标题+摘要 vs 标题”导致的频次失衡
        text = title
        if text:
            texts.append(text)
        if len(texts) >= limit:
            break
    return texts


def fetch_list_titles(url: str, cfg: dict, limit: int) -> list[str]:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    enc = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.content.decode(enc, errors="replace"), "html.parser")
    link_subs = cfg.get("link_match") or []
    title_sels = cfg.get("title_selectors") or []
    title_attr = cfg.get("title_attr")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not any(sub in href for sub in link_subs):
            continue
        title = ""
        if title_attr:
            title = (a.get(title_attr) or "").strip()
        if not title:
            for sel in title_sels:
                node = a.select_one(sel)
                t = node.get_text(" ", strip=True) if node else ""
                if len(t) >= 4:
                    title = t
                    break
        if len(title) < 4:
            continue
        out.append(title)
        if len(out) >= limit:
            break
    return out


def tokenize(text: str) -> list[str]:
    toks: list[str] = []
    for w in jieba.lcut(text):
        w = w.strip().lower()
        if len(w) < 2 or len(w) > 12 or w in _STOPWORDS:
            continue
        if re.fullmatch(r"[\d\W]+", w):
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]+", w) or re.fullmatch(r"[a-z0-9]+", w):
            toks.append(w)
    return toks


def main() -> int:
    parser = argparse.ArgumentParser(description="生成科技/金融领域词候选（人工审核后并入 config/domain_terms.json）")
    parser.add_argument("--per-source", type=int, default=80, help="每个来源最多抓取的篇数")
    parser.add_argument("--top", type=int, default=120, help="每个领域最多输出的候选数")
    parser.add_argument("--min-freq", type=int, default=6, help="候选词最低总频次")
    parser.add_argument("--min-logratio", type=float, default=0.6, help="候选词最低 |log 比率|（判别力门槛）")
    parser.add_argument("--out", default="docs/domain_terms_candidates.md", help="输出 Markdown 路径")
    args = parser.parse_args()

    print("正在抓取科技源（RSS）…")
    tech_texts: list[str] = []
    for name, url in RSS_FEEDS.items():
        try:
            got = fetch_rss_items(url, args.per_source)
            tech_texts += got
            print(f"  {name}: {len(got)} 篇")
        except Exception as exc:
            print(f"  {name}: 失败 {type(exc).__name__}: {exc}")

    print("正在抓取金融源（列表页）…")
    fin_texts: list[str] = []
    for name, cfg in LIST_PAGES.items():
        for page in cfg.get("pages", []):
            try:
                got = fetch_list_titles(page, cfg, args.per_source)
                fin_texts += got
                print(f"  {name}: {len(got)} 条")
            except Exception as exc:
                print(f"  {name}: 失败 {type(exc).__name__}: {exc}")

    tech_counter: Counter[str] = Counter()
    fin_counter: Counter[str] = Counter()
    tech_example: dict[str, str] = {}
    fin_example: dict[str, str] = {}
    for text in tech_texts:
        for w in set(tokenize(text)):
            tech_counter[w] += 1
            tech_example.setdefault(w, text[:60])
    for text in fin_texts:
        for w in set(tokenize(text)):
            fin_counter[w] += 1
            fin_example.setdefault(w, text[:60])

    known = {t.lower() for terms in DOMAIN_TERMS.values() for t in terms}
    rows: list[tuple[str, float, int, int, int, str]] = []
    for w in set(tech_counter) | set(fin_counter):
        t = tech_counter.get(w, 0)
        f = fin_counter.get(w, 0)
        total = t + f
        if total < args.min_freq:
            continue
        lr = math.log((t + 1) / (f + 1))
        if abs(lr) < args.min_logratio:
            continue
        rows.append(("科技" if lr > 0 else "金融", abs(lr), total, t, f, w))
    rows.sort(key=lambda x: (-x[1], -x[2]))

    def render(section: str) -> list[str]:
        lines = [f"## {section}候选（人工审核）", "", "| 词 | 权重建议 | 科技频次 | 金融频次 | 判别力 | 示例 |", "|---|---|---|---|---|---|"]
        picked = [r for r in rows if r[0] == section][: args.top]
        for bias, lr, total, t, f, w in picked:
            is_known = w in known
            weight = "2/已收录" if is_known else "1/待定"
            example = (tech_example.get(w) or fin_example.get(w) or "").replace("|", "｜").replace("\n", " ")
            lines.append(f"| {w} | {weight} | {t} | {f} | {lr:.2f} | {example[:36]} |")
        return lines

    out_path = PROJECT_ROOT / args.out
    lines = [
        "# 领域词候选清单（由 scripts/scan_domain_terms.py 生成）",
        "",
        "> 说明：本清单按“领域判别力”自动产出，**需人工审核**后并入 `config/domain_terms.json`。",
        f"> 参数：科技源 {len(RSS_FEEDS)} 个 RSS，金融源 {len(LIST_PAGES)} 个列表页；每源 {args.per_source} 篇；最小频次 {args.min_freq}；|log 比率| ≥ {args.min_logratio}。",
        "",
        f"科技组文本 {len(tech_texts)} 篇 / 金融组文本 {len(fin_texts)} 条。",
        "",
    ]
    lines += render("科技")
    lines += ["", ""]
    lines += render("金融")
    lines += ["", "> 权重建议：2=强（可一票定领域+参与拆词）、1=弱（只参与领域判定）；已收录的词显示为 2/已收录。"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n候选清单已写入 {out_path}（科技 {len([r for r in rows if r[0]=='科技'])} / 金融 {len([r for r in rows if r[0]=='金融'])} 个候选）")
    return 0


if __name__ == "__main__":
    sys.exit(main())