"""研究员角色：只从抓取文本中提取客观事实。"""

from __future__ import annotations

import json

from ..agent.llm import chat_json
from . import prompts


def run_researcher(client, tracker, model: str, topic: str, materials: list[dict],
                   domain: str = "其他"):
    payload = json.dumps({"topic": topic, "materials": materials}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": prompts.researcher_system(domain)},
        {"role": "user", "content": f"分析主题：{topic}\n\n原始材料：\n{payload}"},
    ]
    data, usage = chat_json(client, model, messages, max_tokens=4096)
    if tracker:
        tracker.record(usage)
    return data