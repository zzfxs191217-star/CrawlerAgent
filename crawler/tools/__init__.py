"""工具注册表：集中管理工具的 OpenAI Schema 与本地执行函数。"""

from __future__ import annotations

from . import search, time_tool, web

_TOOLS = {
    "get_current_time": time_tool,
    "fetch_web_page": web,
    "search_news": search,
}


def get_tool_specs() -> list[dict]:
    return [module.SPEC for module in _TOOLS.values()]


def execute_tool(name: str, arguments: dict) -> str:
    module = _TOOLS[name]
    return str(module.run(**arguments))