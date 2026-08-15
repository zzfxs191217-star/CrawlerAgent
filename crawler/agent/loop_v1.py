"""V1.0：ReAct 多步推理 + 工作台账记忆 + 用户可中断。

每轮迭代：思考→行动→观察；动作自动记入台账（JSON 落盘）；
交互模式下每步执行后可暂停询问用户（回车继续 / q 停止 / 输入新指令改方向）。

用法：
    uv run python -m crawler.agent.loop_v1
    uv run python -m crawler.agent.loop_v1 --prompt "请搜索关于百炼平台的最新新闻，抓取其中两篇文章并总结核心观点"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .. import config
from ..tools import execute_tool, get_tool_specs
from .llm import UsageTracker, create_client
from .memory import WorkLedger

SYSTEM_PROMPT = (
    "你是 CrawlerAgent，一个能自主规划并调用工具完成情报收集任务的智能体。\n"
    "工作方式：需要真实数据时先调用工具（搜索新闻、抓取网页、获取时间），"
    "基于工具返回的真实结果推理与回答，不要编造。\n"
    "任务要求抓取并总结多篇文章时，请分步完成：先搜索候选，再抓取正文，最后综合总结。"
)


def _ask_user() -> str:
    print("\n[可中断] 回车=继续 | q=停止 | 输入其他内容=改方向", flush=True)
    try:
        line = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        return "q"
    if line.lower() in {"q", "quit", "停止", "exit"}:
        return "q"
    return line


def run_task(client, tracker, model: str, tools: list[dict], user_input: str,
             ledger: WorkLedger, interactive: bool, timeout: int) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    start = time.time()
    for step in range(config.MAX_AGENT_ITERATIONS):
        if time.time() - start > timeout:
            return "（任务超时，自动中止）"
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=tools, max_tokens=2048
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
            print(f"[思考→行动] 第{step + 1}步 {name}({json.dumps(arguments, ensure_ascii=False)})")
            try:
                result = execute_tool(name, arguments)
            except Exception as exc:
                result = f"工具执行失败：{exc}"
            print(f"[观察] {result[:300]}")
            ledger.record_action(name, arguments, result)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

            if interactive:
                choice = _ask_user()
                if choice == "q":
                    return "（用户已停止任务）"
                if choice:
                    messages.append({"role": "user", "content": choice})
    return "（达到最大迭代次数，任务中止）"


def main() -> int:
    parser = argparse.ArgumentParser(description="CrawlerAgent V1.0 ReAct 多步推理")
    parser.add_argument("--model", default=config.LLM_MODEL_FLASH, help="模型 ID")
    parser.add_argument("--prompt", help="单次执行模式：直接运行该问题后退出")
    parser.add_argument("--timeout", type=int, default=config.AGENT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    client = create_client()
    tracker = UsageTracker()
    tools = get_tool_specs()

    if args.prompt:
        ledger = WorkLedger(task=args.prompt)
        print(f"[任务] {args.prompt}")
        answer = run_task(
            client, tracker, args.model, tools, args.prompt,
            ledger, interactive=False, timeout=args.timeout,
        )
        print(f"\n[最终答复] {answer}")
        ledger.finish(answer)
        print(tracker.summary())
        print(f"台账已保存：{ledger.path}")
        return 0

    print(f"V1.0 智能体（模型：{args.model}）——输入问题，Ctrl+C 退出。")
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
        ledger = WorkLedger(task=user_input)
        print(f"[任务] {user_input}")
        answer = run_task(
            client, tracker, args.model, tools, user_input,
            ledger, interactive=True, timeout=args.timeout,
        )
        print(f"\n[最终答复] {answer}")
        ledger.finish(answer)
        print(tracker.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())