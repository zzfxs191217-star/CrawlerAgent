"""长期记忆/知识库：文档分块 → 向量化 → 余弦检索，JSON 持久化。

用法：
    uv run python -m crawler.memory.store --stats
    uv run python -m crawler.memory.store --index-reports
    uv run python -m crawler.memory.store --query "豆包月活多少" --top-k 3
    uv run python -m crawler.memory.store --add-file 报告.md --source "人工笔记"
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

from .embed import embed_texts

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge"
INDEX_FILE = KNOWLEDGE_DIR / "index.json"
CHUNK_CHARS = 800
CHUNK_OVERLAP = 100


def _chunk_text(text: str, chunk_size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end >= len(text):
            tail = text[start:end].strip()
            if tail:
                chunks.append(tail)
            break
        chunk = text[start:end]
        cut = chunk.rfind("。")
        if cut > chunk_size // 2:
            chunk = chunk[: cut + 1]
            end = start + cut + 1
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class KnowledgeStore:
    def __init__(self, path: Path = INDEX_FILE):
        self.path = Path(path)
        self.data: dict = {"docs": [], "chunks": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {"docs": [], "chunks": []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    def has_document(self, title: str, source: str) -> bool:
        return any(d["title"] == title and d["source"] == source for d in self.data["docs"])

    def doc_count(self) -> int:
        return len(self.data["docs"])

    def chunk_count(self) -> int:
        return len(self.data["chunks"])

    def add_document(self, title: str, text: str, source: str = "") -> int:
        if self.has_document(title, source):
            return 0
        doc_id = f"doc_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.data["docs"].append(
            {
                "id": doc_id,
                "title": title,
                "source": source,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        chunks = _chunk_text(text)
        if not chunks:
            return 0
        vectors = embed_texts(chunks)
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            self.data["chunks"].append(
                {
                    "id": f"{doc_id}_{i}",
                    "doc_id": doc_id,
                    "text": chunk,
                    "embedding": vec,
                }
            )
        self.save()
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.data["chunks"]:
            return []
        qvec = embed_texts([query])[0]
        scored = []
        for chunk in self.data["chunks"]:
            score = _cosine(qvec, chunk["embedding"])
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        docs_by_id = {d["id"]: d for d in self.data["docs"]}
        seen_docs: set[str] = set()
        results = []
        for score, chunk in scored:
            doc = docs_by_id.get(chunk["doc_id"])
            if not doc or doc["id"] in seen_docs:
                continue
            seen_docs.add(doc["id"])
            results.append(
                {
                    "score": round(score, 4),
                    "title": doc["title"],
                    "source": doc["source"],
                    "snippet": chunk["text"][:300],
                }
            )
            if len(results) >= top_k:
                break
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="CrawlerAgent 长期记忆/知识库")
    parser.add_argument("--stats", action="store_true", help="查看统计")
    parser.add_argument("--index-reports", action="store_true", help="把 reports/ 下未入库的报告全部入库")
    parser.add_argument("--add-file", help="把指定文件加入知识库")
    parser.add_argument("--source", default="", help="文档来源（配合 --add-file）")
    parser.add_argument("--query", help="检索问题")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    store = KnowledgeStore()

    if args.stats:
        print(f"文档数：{store.doc_count()}，片段数：{store.chunk_count()}")
        for d in store.data["docs"]:
            print(f"- {d['title']}（来源：{d['source']}，{d['created_at']}）")
        return 0

    if args.index_reports:
        reports_dir = Path(__file__).resolve().parent.parent.parent / "reports"
        if not reports_dir.exists():
            print("没有 reports 目录。")
            return 0
        added = 0
        for md in sorted(reports_dir.glob("*.md")):
            if store.has_document(md.stem, "report"):
                continue
            n = store.add_document(md.stem, md.read_text(encoding="utf-8"), "report")
            print(f"已入库：{md.name}（{n} 个片段）")
            added += 1
        print(f"共新增 {added} 篇报告。")
        return 0

    if args.add_file:
        fp = Path(args.add_file)
        if not fp.exists():
            print(f"文件不存在：{fp}")
            return 1
        n = store.add_document(fp.stem, fp.read_text(encoding="utf-8"), args.source or "本地文件")
        print(f"已入库 {n} 个片段：{fp.name}")
        return 0

    if args.query:
        results = store.search(args.query, args.top_k)
        if not results:
            print("知识库为空或没有相关结果。")
            return 0
        for i, r in enumerate(results, start=1):
            print(f"{i}. [{r['score']}] {r['title']}（来源：{r['source']}）")
            print(f"   {r['snippet']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())