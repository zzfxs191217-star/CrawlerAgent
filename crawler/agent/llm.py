"""百炼 OpenAI 兼容接口封装 + token 用量记账。"""

from __future__ import annotations

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