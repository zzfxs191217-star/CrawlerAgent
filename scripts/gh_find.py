"""GitHub 参考项目检索工具（无代理直连）。

用途：按关键词搜索 GitHub（或 Gitee）上可借鉴的开源项目，输出
项目名、Stars、语言、描述、链接，并追加写入 docs/references.md。

用法：
    python scripts/gh_find.py "llm agent" "react agent"
    python scripts/gh_find.py --engine gitee "智能体 爬虫"
    python scripts/gh_find.py --no-save "web scraper"

说明：
    - 默认走 GitHub 公开搜索 API（无需 token，限流较低）。
    - --engine gitee 切换为 Gitee 搜索 API（国内更稳）。
    - 结果默认保存到 docs/references.md，--no-save 只打印。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

USER_AGENT = "CrawlerAgent-reference-tool/0.1"

ENGINES = {
    "github": "https://api.github.com/search/repositories",
    "gitee": "https://gitee.com/api/v5/search/repositories",
}

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_FILE = REPO_ROOT / "docs" / "references.md"


def fetch_json(url: str, timeout: int = 15) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _normalize_rows(data: object) -> list[dict]:
    """兼容 GitHub({items:[...]}) 与 Gitee(数组 或 {data:[...]}) 的返回结构。"""
    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or []
    elif isinstance(data, list):
        items = data
    else:
        items = []
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("full_name") or item.get("name") or "",
                "stars": item.get("stargazers_count") or item.get("stars_count") or 0,
                "lang": item.get("language") or "-",
                "desc": (item.get("description") or "").strip().replace("|", "/"),
                "url": item.get("html_url") or item.get("url") or "",
                "updated": (item.get("updated_at") or "")[:10],
            }
        )
    return rows


def search(engine: str, keyword: str, per_page: int) -> list[dict]:
    base = ENGINES[engine]
    params = {"q": keyword, "per_page": str(per_page)}
    if engine == "github":
        params.update({"sort": "stars", "order": "desc"})
    else:
        params.update({"sort": "stars_count", "order": "desc"})
    url = f"{base}?{urllib.parse.urlencode(params)}"
    return _normalize_rows(fetch_json(url))


def render_rows(rows: list[dict]) -> str:
    lines = ["| 项目 | Stars | 语言 | 说明 | 链接 | 更新 |", "|---|---|---|---|---|---|"]
    for r in rows:
        desc = (r["desc"] or "-")[:80]
        lines.append(
            f"| {r['name']} | {r['stars']} | {r['lang']} | {desc} | {r['url']} | {r['updated']} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub/Gitee 参考项目检索（无代理）")
    parser.add_argument("keywords", nargs="+", help="搜索关键词，可多个")
    parser.add_argument("--engine", choices=sorted(ENGINES), default="github")
    parser.add_argument("--per-page", type=int, default=6)
    parser.add_argument("--no-save", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    today = date.today().isoformat()
    blocks = [f"\n## {today} 检索（engine={args.engine}）\n"]
    failed = 0

    for kw in args.keywords:
        print(f"\n===== {kw}（{args.engine}） =====")
        try:
            rows = search(args.engine, kw, args.per_page)
        except urllib.error.HTTPError as exc:
            print(f"  [失败] HTTP {exc.code}：限流或网络问题，稍后重试")
            failed += 1
            continue
        except Exception as exc:
            print(f"  [失败] {exc}")
            failed += 1
            continue
        if not rows:
            print("  （无结果）")
            continue
        block = f"\n### 关键词：{kw}\n\n{render_rows(rows)}\n"
        blocks.append(block)
        print(render_rows(rows))

    if not args.no_save and len(blocks) > 1:
        REFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with REFERENCES_FILE.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(blocks))
        print(f"\n已追加保存到 {REFERENCES_FILE}")

    print(f"\n完成：{len(args.keywords)} 个关键词，失败 {failed} 个")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())