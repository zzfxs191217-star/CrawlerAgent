"""审查员角色：核对分析结论是否有事实证据支撑，防幻觉。"""

from __future__ import annotations

import json

from ..agent.llm import chat_json
from . import prompts


def run_reviewer(client, tracker, model: str, topic: str, analysis: dict, facts: list[dict]):
    payload = json.dumps(
        {"topic": topic, "facts": facts, "analysis": analysis}, ensure_ascii=False
    )
    messages = [
        {"role": "system", "content": prompts.REVIEWER_SYSTEM},
        {"role": "user", "content": f"请核对以下分析的证据支撑情况：\n{payload}"},
    ]
    data, usage = chat_json(client, model, messages, max_tokens=4096)
    if tracker:
        tracker.record(usage)
    return data