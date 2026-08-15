"""长期记忆工具：在历史报告与知识条目中检索相关内容。"""

from __future__ import annotations

from ..memory.store import KnowledgeStore

SPEC = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": (
            "在项目的长期记忆库（历史分析报告与知识条目）中检索相关内容，"
            "返回相关片段、标题与来源。适合在分析前查看历史结论。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索问题或关键词"},
                "top_k": {"type": "integer", "description": "返回条数，默认 3", "default": 3},
            },
            "required": ["query"],
        },
    },
}


def run(query: str, top_k: int = 3) -> str:
    results = KnowledgeStore().search(query, top_k=max(1, min(int(top_k), 10)))
    if not results:
        return "知识库中没有相关内容。"
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(
            f"{i}. {r['title']}（来源：{r['source']}，相似度 {r['score']}）\n"
            f"   {r['snippet']}"
        )
    return "知识库检索结果：\n" + "\n".join(lines)