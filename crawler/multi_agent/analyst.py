"""分析师角色：基于研究员事实进行竞争态势分析。"""

from __future__ import annotations

import json

from ..agent.llm import chat_json
from . import prompts


def run_analyst(client, tracker, model: str, topic: str, facts: list[dict], feedback: str | None = None):
    payload = json.dumps({"topic": topic, "facts": facts}, ensure_ascii=False)
    messages = [
        {"role": "system", "content": prompts.ANALYST_SYSTEM},
        {"role": "user", "content": f"分析主题：{topic}\n\n研究员提炼的事实：\n{payload}"},
    ]
    if feedback:
        messages.append(
            {"role": "user", "content": f"审查员反馈（请据此修正你的分析）：\n{feedback}"}
        )
    data, usage = chat_json(client, model, messages, max_tokens=4096)
    if tracker:
        tracker.record(usage)
    return data