"""V0.0：单工具调用闭环。

用户输入自然语言 → 模型决定调用工具 → 本地执行 → 结果回传模型 → 最终答复。

用法：
    uv run python -m crawler.agent.loop_v0
    uv run python -m crawler.agent.loop_v0 --prompt "帮我抓取百度首页的标题"
    uv run python -m crawler.agent.loop_v0 --model qwen3.5-omni-plus-2026-03-15
"""

from __future__ import annotations

import argparse
import json
import sys

from .. import config
from ..tools import execute_tool, get_tool_specs
from .llm import UsageTracker, create_client

SYSTEM_PROMPT = (
    "你是 CrawlerAgent，一个可以调用工具完成任务的情报助手。"
    "当用户请求需要真实数据时，先调用合适的工具获取结果，再基于真实结果回答；不要凭空编造。"
)

MAX_ITERATIONS = 8


def run_task(client, tracker, model: str, tools: list[dict], user_input: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    for _ in range(MAX_ITERATIONS):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=tools, max_tokens=1024
        )
        tracker.record(resp.usage)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return (msg.content or "").strip()

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in msg.tool_calls
                ],
            }
        )
        for call in msg.tool_calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            print(f"[行动] {name}({json.dumps(arguments, ensure_ascii=False)})")
            try:
                result = execute_tool(name, arguments)
            except Exception as exc:
                result = f"工具执行失败：{exc}"
            print(f"[观察] {result[:200]}")
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": result}
            )
    return "（达到最大迭代次数，任务中止）"


def main() -> int:
    parser = argparse.ArgumentParser(description="CrawlerAgent V0.0 单工具调用闭环")
    parser.add_argument("--model", default=config.LLM_MODEL_FLASH, help="模型 ID")
    parser.add_argument("--prompt", help="单次执行模式：直接运行该问题后退出")
    args = parser.parse_args()

    client = create_client()
    tracker = UsageTracker()
    tools = get_tool_specs()

    if args.prompt:
        print(f"[任务] {args.prompt}")
        answer = run_task(client, tracker, args.model, tools, args.prompt)
        print(f"[答复] {answer}")
        print(tracker.summary())
        return 0

    print(f"V0.0 智能体（模型：{args.model}）——输入问题，Ctrl+C 退出。")
    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "退出"}:
            break
        print(f"[任务] {user_input}")
        answer = run_task(client, tracker, args.model, tools, user_input)
        print(f"[答复] {answer}")
        print(tracker.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())