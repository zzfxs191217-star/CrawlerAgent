"""阶段一：百炼模型连通性测试。

读取 .env 配置，通过 OpenAI 兼容接口调用模型，打印模型回复与 token 用量。
用法：uv run python scripts/connectivity_test.py [模型ID]
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL")
API_KEY = os.getenv("DASHSCOPE_API_KEY")
DEFAULT_MODEL = os.getenv("LLM_MODEL_PLUS", "qwen3.5-omni-plus-2026-03-15")

if not BASE_URL or not API_KEY:
    raise SystemExit("请先配置 .env（参考 .env.example）：LLM_BASE_URL 与 DASHSCOPE_API_KEY")

model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
print(f"目标模型：{model}")
print(f"接口地址：{BASE_URL}")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "请用一两句话介绍你自己：你是谁、能做什么。"}],
    max_tokens=512,
)

content = resp.choices[0].message.content
print(f"\n模型回复：{content}")
if resp.usage:
    u = resp.usage
    print(f"Token 用量：prompt={u.prompt_tokens} completion={u.completion_tokens} total={u.total_tokens}")