"""CrawlerAgent Web 界面（V3.1）：浏览器里运行完整分析、查看报告、检索知识库。

用法：
    uv run python -m crawler.webui
    然后浏览器打开 http://127.0.0.1:7860
"""

from __future__ import annotations

import gradio as gr

from .multi_agent.orchestration import run_pipeline


def run_analysis(topic: str, progress=gr.Progress()):
    """执行完整分析流水线，返回报告 Markdown、文件路径与 Token 用量。"""
    topic = (topic or "").strip()
    if not topic:
        raise gr.Error("请先输入一个分析课题，例如：分析字节跳动旗下豆包与阿里通义千问的竞争态势")

    progress(0.02, desc="准备开始…")

    def on_progress(msg: str, frac: float | None) -> None:
        if frac is not None:
            progress(frac, desc=msg)

    try:
        result = run_pipeline(topic, progress=on_progress)
    except RuntimeError as exc:
        raise gr.Error(str(exc))

    report_path = str(result["report_path"])
    note = result["knowledge_note"]
    footer = f"> 报告已保存：`{report_path}` ｜ {note}"
    return result["report"] + "\n\n" + footer, report_path, result["tracker"].summary()


def search_memory(query: str, top_k: int = 5):
    """在长期记忆知识库中检索相关内容。"""
    query = (query or "").strip()
    if not query:
        raise gr.Error("请输入检索问题，例如：豆包月活多少？")
    from .memory.store import KnowledgeStore

    results = KnowledgeStore().search(query, top_k=int(top_k))
    if not results:
        return "知识库为空或没有相关结果。可以先跑一次「分析报告」再回来检索。"
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(
            f"{i}. **{r['title']}**（来源：{r['source']}，相似度 {r['score']}）\n\n> {r['snippet']}\n"
        )
    return "\n\n".join(lines)


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
            run_btn = gr.Button("开始分析", variant="primary")
            report_md = gr.Markdown(label="分析报告")
            path_out = gr.Textbox(label="报告文件路径", interactive=False, lines=1)
            tokens_out = gr.Textbox(label="Token 用量", interactive=False, lines=1)
            run_btn.click(
                run_analysis,
                inputs=[topic],
                outputs=[report_md, path_out, tokens_out],
            )
            gr.Markdown("> 提示：一次完整分析约需 3–5 分钟，期间请勿关闭页面。")
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
        gr.Markdown("模型：qwen3.7-flash（收集/整理）+ qwen3.5-omni-plus（分析/审查）｜长期记忆：text-embedding-v3")
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