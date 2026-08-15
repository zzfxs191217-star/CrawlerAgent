"""项目配置：从 .env 读取百炼端点、密钥与模型 ID。"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
LLM_MODEL_FLASH = os.getenv("LLM_MODEL_FLASH", "qwen3.7-flash-2026-07-15")
LLM_MODEL_PLUS = os.getenv("LLM_MODEL_PLUS", "qwen3.5-omni-plus-2026-03-15")