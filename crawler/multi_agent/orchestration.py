"""V2.0 多角色协作编排：资料收集 → 研究员 → 分析师 → 审查员 → Markdown 报告。

用法：
    uv run python -m crawler.multi_agent.orchestration --topic "分析字节跳动旗下豆包与阿里通义千问的竞争态势"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from .. import config
from ..agent.llm import UsageTracker, create_client
from ..tools import execute_tool, get_tool_specs
from . import prompts
from .analyst import run_analyst
from .researcher import run_researcher
from .reviewer import run_reviewer

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
MAX_REVISION_ROUNDS = 2


class PipelineCancelled(RuntimeError):
    """分析任务被用户取消（Web 界面取消按钮触发）。"""

GATHER_SYSTEM = (
    "你是 CrawlerAgent 的情报收集员。根据分析主题搜索相关新闻报道并抓取正文，"
    "最多搜索 2 次、抓取 2-3 篇正文后立即停止。优先选择可信来源（白名单媒体、官方渠道）。"
)


def _parse_fetch_result(result: str) -> tuple[str, str]:
    m = re.match(r"^标题：(.*)\n正文（\d+ 字符）：\n([\s\S]*)$", result)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", result


def gather_materials(client, tracker, model: str, tools: list[dict], topic: str, timeout: int,
                     cancelled=None) -> list[dict]:
    messages = [
        {"role": "system", "content": GATHER_SYSTEM},
        {"role": "user", "content": f"分析主题：{topic}\n请搜索相关新闻并抓取 2-3 篇正文质量良好的文章。"},
    ]
    materials: list[dict] = []
    seen: set[str] = set()
    start = time.time()
    for step in range(config.MAX_AGENT_ITERATIONS):
        if cancelled is not None and cancelled():
            raise PipelineCancelled("任务已被用户取消")
        if time.time() - start > timeout:
            break
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=tools, max_tokens=2048
        )
        tracker.record(resp.usage)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
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
            print(f"[收集] 第{step + 1}步 {name}({json.dumps(arguments, ensure_ascii=False)})")
            try:
                result = execute_tool(name, arguments)
            except Exception as exc:
                result = f"工具执行失败：{exc}"
            print(f"[观察] {result[:150]}")
            if name == "fetch_web_page":
                url = arguments.get("url", "")
                title, body = _parse_fetch_result(result)
                if url and url not in seen and len(body) >= 200:
                    seen.add(url)
                    materials.append({"url": url, "title": title, "text": body[:4000]})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return materials


def _md_cell(value: str) -> str:
    """表格单元格里的竖线替换为全角，避免破坏 Markdown 表格。"""
    return str(value).replace("|", "｜")


def _as_list(data: dict, key: str) -> list:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def assemble_report(topic: str, materials: list[dict], facts: dict, analysis: dict,
                    review: dict, model: str, tracker: UsageTracker) -> str:
    facts_list = _as_list(facts, "facts")
    conclusions = _as_list(analysis, "conclusions")
    swot = analysis.get("swot", {}) if isinstance(analysis.get("swot"), dict) else {}
    review_items = _as_list(review, "items")

    lines = [
        f"# {topic}",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 模型：{model} | {tracker.summary()}",
        "",
        "## 一、资料清单",
        "",
        "| # | 标题 | 来源 | 链接 |",
        "|---|---|---|---|",
    ]
    for i, m in enumerate(materials, start=1):
        domain = re.sub(r"^https?://", "", m.get("url", "")).split("/")[0]
        lines.append(f"| {i} | {_md_cell(m.get('title', '')[:40])} | {_md_cell(domain)} | {_md_cell(m.get('url', ''))} |")

    lines += ["", "## 二、事实提炼", ""]
    if facts_list:
        for i, f in enumerate(facts_list, start=1):
            lines.append(f"{i}. {f.get('statement', '')}（来源：{f.get('source_url', '')}）")
    else:
        lines.append("（无事实条目）")

    lines += ["", "## 三、SWOT 分析", ""]
    for label, key in [("优势", "strengths"), ("劣势", "weaknesses"), ("机会", "opportunities"), ("威胁", "threats")]:
        lines.append(f"### {label}")
        items = swot.get(key, [])
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("- （无）")

    lines += ["", "## 四、主要结论", ""]
    if conclusions:
        for i, c in enumerate(conclusions, start=1):
            evidence = "；".join(c.get("evidence", [])) if isinstance(c.get("evidence"), list) else c.get("evidence", "")
            lines.append(f"{i}. **{c.get('conclusion', '')}**" + (f"\n   - 依据：{evidence}" if evidence else ""))
    else:
        lines.append("（无结论条目）")

    lines += ["", "## 五、审查结果", ""]
    lines.append(f"整体判定：**{review.get('overall', 'unknown')}**")
    if review_items:
        for item in review_items:
            lines.append(f"- [{item.get('verdict', '?')}] {item.get('conclusion', '')} — {item.get('note', '')}")
    if review.get("feedback"):
        lines.append(f"- 修正意见：{review.get('feedback')}")

    lines += ["", "## 六、引用来源", ""]
    for m in materials:
        lines.append(f"- [{m.get('title', '')[:50]}]({m.get('url', '')})")

    return "\n".join(lines)


def run_pipeline(topic: str, gather_model: str = config.LLM_MODEL_FLASH,
                 model: str = config.LLM_MODEL_PLUS, timeout: int = 300,
                 progress=None, out_dir: Path | None = None, cancelled=None) -> dict:
    """执行完整分析流水线（资料收集→研究员→分析师→审查员→报告），返回结果字典。

    progress 为可选回调，签名：progress(message: str, fraction: float | None)。
    """
    client = create_client()
    tracker = UsageTracker()
    tools = get_tool_specs()

    def _report(msg: str, frac: float | None = None) -> None:
        print(msg)
        if progress is not None:
            try:
                progress(msg, frac)
            except Exception:
                pass

    def _check() -> None:
        if cancelled is not None and cancelled():
            raise PipelineCancelled("任务已被用户取消")

    _report(f"[1/5] 资料收集（模型：{gather_model}）", 0.05)
    _check()
    materials = gather_materials(client, tracker, gather_model, tools, topic, timeout, cancelled)
    if not materials:
        raise RuntimeError("未收集到可用材料，任务中止。请换个课题或稍后再试。")
    _check()
    _report(f"已收集 {len(materials)} 篇材料", 0.3)

    _report("[2/5] 研究员提炼事实…", 0.4)
    _check()
    facts = run_researcher(client, tracker, model, topic, materials)
    _check()

    _report("[3/5] 分析师竞争态势分析…", 0.6)
    _check()
    analysis = run_analyst(client, tracker, model, topic, _as_list(facts, "facts"))
    _check()

    _report("[4/5] 审查员证据核验…", 0.75)
    _check()
    review = run_reviewer(client, tracker, model, topic, analysis, _as_list(facts, "facts"))
    rounds = 0
    while review.get("overall") == "revise" and rounds < MAX_REVISION_ROUNDS:
        rounds += 1
        _check()
        _report(f"[审查] 第 {rounds} 轮修正：{review.get('feedback', '')}", 0.75 + 0.06 * rounds)
        analysis = run_analyst(client, tracker, model, topic, _as_list(facts, "facts"),
                               feedback=review.get("feedback"))
        review = run_reviewer(client, tracker, model, topic, analysis, _as_list(facts, "facts"))

    _check()
    _report("[5/5] 生成报告并写入长期记忆…", 0.9)
    report_md = assemble_report(topic, materials, facts, analysis, review, model, tracker)
    reports_dir = out_dir or REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", topic).strip("_")[:40]
    report_path = reports_dir / f"{slug}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    report_path.write_text(report_md, encoding="utf-8")

    knowledge_note = ""
    try:
        from ..memory.store import KnowledgeStore

        added = KnowledgeStore().add_document(topic, report_md, "report")
        knowledge_note = f"已加入长期记忆库（{added} 个片段）"
        print(knowledge_note)
    except Exception as exc:
        knowledge_note = f"记忆库入库失败（不影响报告）：{exc}"
        print(knowledge_note)

    _report(f"报告已生成：{report_path}", 1.0)
    return {
        "report": report_md,
        "report_path": report_path,
        "tracker": tracker,
        "materials": materials,
        "facts": facts,
        "analysis": analysis,
        "review": review,
        "knowledge_note": knowledge_note,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="CrawlerAgent V2.0 多角色协作报告生成")
    parser.add_argument("--topic", required=True, help="分析课题，例如：分析字节跳动旗下豆包与阿里通义千问的竞争态势")
    parser.add_argument("--model", default=config.LLM_MODEL_PLUS, help="分析/审查模型（默认 omni-plus）")
    parser.add_argument("--gather-model", default=config.LLM_MODEL_FLASH, help="资料收集模型（默认 flash）")
    parser.add_argument("--timeout", type=int, default=300, help="资料收集超时秒数")
    parser.add_argument("--export", default="", help="报告导出格式（逗号分隔）：pdf/docx，例如 --export pdf,docx")
    args = parser.parse_args()

    try:
        result = run_pipeline(args.topic, args.gather_model, args.model, args.timeout)
    except RuntimeError as exc:
        print(exc)
        return 1

    if args.export:
        from ..export import export_report
        fmts = [f.strip() for f in args.export.split(",") if f.strip()]
        try:
            exported = export_report(result["report"], result["report_path"].stem, REPORTS_DIR, fmts=fmts)
            for fmt, path_out in exported.items():
                print(f"已导出 {fmt.upper()}：{path_out}")
        except Exception as exc:
            print(f"导出失败（不影响报告）：{exc}")

    print(f"\n{result['tracker'].summary()}")
    print("\n报告预览：")
    print("\n".join(result["report"].splitlines()[:40]))
    return 0

if __name__ == "__main__":
    sys.exit(main())