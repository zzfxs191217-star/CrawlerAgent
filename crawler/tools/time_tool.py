"""时间工具：获取当前系统时间。"""

from __future__ import annotations

from datetime import datetime

SPEC = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取当前本地系统时间，返回格式为 YYYY-MM-DD HH:MM:SS。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


def run() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")