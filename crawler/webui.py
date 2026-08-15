"""CrawlerAgent Web 界面（V3.1）：浏览器里运行完整分析、查看报告、导出 PDF/Word、检索知识库。

用法：
    uv run python -m crawler.webui
    然后浏览器打开 http://127.0.0.1:7860
"""

from __future__ import annotations

import threading
from pathlib import Path

import gradio as gr

from . import config
from .memory.store import KnowledgeStore
from .multi_agent.orchestration import PipelineCancelled, run_pipeline

# 取消标志：点击“取消任务”置位，流水线在步骤间轮询后抛出 PipelineCancelled。
_cancel_event = threading.Event()

TOPIC_GUIDE_MD = """### 选题指南（提高成功率）

1. **热点优先**：选最近 1-2 周有媒体持续报道的方向，白名单媒体（科技/AI 向）更容易抓到。
2. **2 个对象对比**：先做 A vs B，成功率远高于一次对比 3 个产品（例如 QQ音乐/网易云/汽水音乐一次对比）。
3. **用官方产品名**：如「网易云音乐」而不是「网抑云」；别把多个产品挤在一个关键词里。
4. **先预检再开跑**：点「预检选题」，1 分钟就知道有没有料，别直接跑 5 分钟完整分析。
5. **失败常见原因**：数据源不覆盖该领域（音乐/文娱/消费类）、话题过冷、对象过多、命名不规范。
6. **领域定制**：科技/金融选题会自动套用对应分析维度（科技=技术路线/生态/商业化；金融=市场规模/监管/风险/资本开支），预检结果会显示领域判定。
"""


def run_analysis(topic: str, gather_model: str, model: str, progress=gr.Progress()):
    """执行完整分析流水线，返回报告 Markdown、文件路径、Token 用量与可下载文件。"""
    topic = (topic or "").strip()
    if not topic:
        raise gr.Error("请先输入一个分析课题，例如：分析字节跳动旗下豆包与阿里通义千问的竞争态势")

    _cancel_event.clear()
    progress(0.02, desc="准备开始…")

    def on_progress(msg: str, frac: float | None) -> None:
        if frac is not None:
            progress(frac, desc=msg)

    try:
        result = run_pipeline(
            topic,
            gather_model=gather_model,
            model=model,
            progress=on_progress,
            cancelled=lambda: _cancel_event.is_set(),
        )
    except PipelineCancelled:
        raise gr.Error("任务已取消，可重新开始。")
    except RuntimeError as exc:
        raise gr.Error(str(exc))

    report_path = str(result["report_path"])
    note = result["knowledge_note"]
    footer = f"> 报告已保存：`{report_path}` ｜ {note}"
    return result["report"] + "\n\n" + footer, report_path, result["tracker"].summary(), report_path


def request_cancel() -> str:
    _cancel_event.set()
    return "已请求取消：当前步骤结束后会停止，约 3–5 秒内生效。"


def export_report_file(report_path: str, fmt: str) -> tuple[str, str]:
    """把已生成的报告导出为 PDF/Word，返回（文件路径, 状态文字）。"""
    from .export import export_report

    report_path = (report_path or "").strip()
    if not report_path:
        raise gr.Error("请先运行一次分析生成报告，再导出文件")
    p = Path(report_path)
    if not p.exists():
        raise gr.Error(f"报告文件不存在：{report_path}")
    exported = export_report(p.read_text(encoding="utf-8"), p.stem, p.parent, fmts=[fmt])
    f = exported[fmt]
    return str(f), f"已导出 {fmt.upper()}：{f}"


def export_pdf(report_path: str) -> tuple[str, str]:
    return export_report_file(report_path, "pdf")


def export_docx(report_path: str) -> tuple[str, str]:
    return export_report_file(report_path, "docx")


def search_memory(query: str, top_k: int = 5):
    """在长期记忆知识库中检索相关内容。"""
    query = (query or "").strip()
    if not query:
        raise gr.Error("请输入检索问题，例如：豆包月活多少？")
    results = KnowledgeStore().search(query, top_k=int(top_k))
    if not results:
        return "知识库为空或没有相关结果。可以先跑一次「分析报告」再回来检索。"
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(
            f"{i}. **{r['title']}**（来源：{r['source']}，相似度 {r['score']}）\n\n> {r['snippet']}\n"
        )
    return "\n\n".join(lines)


def precheck_topic(topic: str) -> tuple[str, str]:
    """选题预检：返回（领域判定标签, 预检 Markdown）。"""
    from .topic_check import check_topic, format_report

    topic = (topic or "").strip()
    if not topic:
        raise gr.Error("请输入课题或关键词，例如：豆包 通义千问")
    info = check_topic(topic)
    domain = info.get("domain", "其他")
    domain_label = {
        "科技": "领域判定：科技（技术路线/生态/产品/商业化维度）",
        "金融": "领域判定：金融（市场规模/监管/风险/资本开支维度）",
        "综合": "领域判定：综合（科技+金融维度）",
        "其他": "领域判定：其他（市场/竞争/风险/趋势维度）",
    }.get(domain, f"领域判定：{domain}")
    return domain_label, format_report(info)


def fill_topic(topic: str) -> str:
    """把预检通过的课题填入「分析报告」页签。"""
    return (topic or "").strip()


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="CrawlerAgent 竞品情报分析") as demo:
        gr.Markdown(
            "# CrawlerAgent 竞品情报分析\n"
            "输入公司名/产品名，自动完成：搜索新闻 → 抓取正文 → 多角色分析 → 输出带引用来源的 Markdown 报告。\n\n"
            "**密钥安全：API Key 只保存在服务端 `.env`，不会下发到浏览器。**"
        )
        with gr.Tab("分析报告"):
            topic = gr.Textbox(
                label="分析课题",
                placeholder="例如：分析字节跳动旗下豆包与阿里通义千问的竞争态势",
                lines=2,
            )
            with gr.Row():
                gather_model = gr.Dropdown(
                    choices=[config.LLM_MODEL_FLASH, config.LLM_MODEL_PLUS],
                    value=config.LLM_MODEL_FLASH,
                    label="收集/整理模型",
                )
                model = gr.Dropdown(
                    choices=[config.LLM_MODEL_PLUS, config.LLM_MODEL_FLASH],
                    value=config.LLM_MODEL_PLUS,
                    label="分析/审查模型",
                )
            with gr.Row():
                run_btn = gr.Button("开始分析", variant="primary")
                cancel_btn = gr.Button("取消任务", variant="stop")
            cancel_status = gr.Textbox(label="状态", interactive=False, lines=1)
            report_md = gr.Markdown(label="分析报告")
            with gr.Row():
                path_out = gr.Textbox(label="报告文件路径", interactive=False, lines=1)
                tokens_out = gr.Textbox(label="Token 用量", interactive=False, lines=1)
            report_file = gr.File(label="下载 Markdown 报告", interactive=False)
            run_btn.click(
                run_analysis,
                inputs=[topic, gather_model, model],
                outputs=[report_md, path_out, tokens_out, report_file],
            )
            cancel_btn.click(request_cancel, outputs=[cancel_status])
            with gr.Row():
                pdf_btn = gr.Button("导出 PDF")
                docx_btn = gr.Button("导出 Word")
            export_file = gr.File(label="导出文件", interactive=False)
            export_status = gr.Textbox(label="导出状态", interactive=False, lines=1)
            pdf_btn.click(export_pdf, inputs=[path_out], outputs=[export_file, export_status])
            docx_btn.click(export_docx, inputs=[path_out], outputs=[export_file, export_status])
            gr.Markdown("> 提示：一次完整分析约需 3–5 分钟；「取消任务」会在当前步骤结束后停止；导出前请先生成报告。")
        with gr.Tab("知识库检索"):
            query = gr.Textbox(
                label="检索问题",
                placeholder="例如：豆包月活多少？",
                lines=2,
            )
            top_k = gr.Slider(1, 10, value=5, step=1, label="返回条数")
            search_btn = gr.Button("检索", variant="primary")
            result_md = gr.Markdown(label="检索结果")
            search_btn.click(search_memory, inputs=[query, top_k], outputs=[result_md])
        with gr.Tab("选题助手"):
            gr.Markdown(TOPIC_GUIDE_MD)
            ptopic = gr.Textbox(
                label="想分析的课题",
                placeholder="例如：分析字节跳动旗下豆包与阿里通义千问的竞争态势",
                lines=2,
            )
            with gr.Row():
                precheck_btn = gr.Button("预检选题", variant="primary")
                go_btn = gr.Button("有料？去生成报告", variant="secondary")
            domain_out = gr.Textbox(label="领域判定", interactive=False, lines=1)
            precheck_out = gr.Markdown(label="预检结果")
            precheck_btn.click(precheck_topic, inputs=[ptopic], outputs=[domain_out, precheck_out])
            go_btn.click(fill_topic, inputs=[ptopic], outputs=[topic])
        gr.Markdown(
            f"模型：{config.LLM_MODEL_FLASH}（收集/整理）+ {config.LLM_MODEL_PLUS}（分析/审查）｜长期记忆：text-embedding-v3"
        )
    return demo


def main() -> None:
    demo = build_demo()
    demo.queue(default_concurrency_limit=2).launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        inbrowser=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()