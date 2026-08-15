"""百炼 OpenAI 兼容接口封装 + token 用量记账。"""

from __future__ import annotations

import json
import re

from openai import OpenAI

from .. import config


class UsageTracker:
    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def record(self, usage) -> None:
        if usage:
            self.prompt_tokens += usage.prompt_tokens or 0
            self.completion_tokens += usage.completion_tokens or 0

    def summary(self) -> str:
        total = self.prompt_tokens + self.completion_tokens
        return f"Token 用量：prompt={self.prompt_tokens} completion={self.completion_tokens} total={total}"


def create_client() -> OpenAI:
    if not config.LLM_BASE_URL or not config.DASHSCOPE_API_KEY:
        raise SystemExit(
            "请先配置 .env（参考 .env.example）：LLM_BASE_URL 与 DASHSCOPE_API_KEY"
        )
    return OpenAI(api_key=config.DASHSCOPE_API_KEY, base_url=config.LLM_BASE_URL)


def _extract_json(text: str):
    """从模型输出中稳健提取 JSON 对象：处理围栏与多余文本。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
    if text.endswith("```"):
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def chat_json(client, model: str, messages: list[dict], max_tokens: int = 4096):
    """调用模型并要求返回 JSON，返回 (data, usage)。解析失败时返回 {"_raw": 原文}。"""
    kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
    try:
        resp = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception:
        resp = client.chat.completions.create(**kwargs)
    usage = resp.usage
    text = (resp.choices[0].message.content or "").strip()
    data = _extract_json(text)
    if data is None:
        return {"_raw": text}, usage
    return data, usage