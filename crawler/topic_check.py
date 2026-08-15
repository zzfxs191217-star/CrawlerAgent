"""选题助手：分析前预检课题在白名单媒体中的覆盖情况，给出“有料/偏少/没料”判断与建议。

用法（命令行）：
    uv run python -m crawler.topic_check --topic "分析字节跳动旗下豆包与阿里通义千问的竞争态势"
"""

from __future__ import annotations

import argparse
import sys

from .tools.search import BROAD_COMPANIES, domain_of, search_candidates

# 相关度阈值：原词命中正文 +2 即视为真正相关；仅 2-gram 命中（<2）视为噪音
RELEVANT_SCORE = 2.0


def check_topic(topic: str, top_k: int = 5) -> dict:
    """预检课题覆盖情况。返回 verdict: ok / warn / none，以及候选与建议。"""
    domain = domain_of(topic)
    candidates, failed = search_candidates(topic, count=10)
    # 真正相关：分数达标 + 命中具体实体词，且不只在母公司级命中（如“腾讯”）
    relevant = [
        c for c in candidates
        if c["score"] >= RELEVANT_SCORE
        and c.get("matched")
        and any(t not in BROAD_COMPANIES for t in c["matched"])
    ]
    top = relevant[:top_k] if relevant else candidates[:top_k]

    if len(relevant) >= 3:
        verdict = "ok"
        message = (
            f"✅ 有料（领域：{domain}）：白名单媒体近期找到 {len(candidates)} 条相关候选，"
            f"其中 {len(relevant)} 条真正相关，可以开跑。"
        )
        suggestions = [
            "用官方产品名做关键词，并把对比对象控制在 2 个以内，成功率更高。",
            "若想覆盖更多角度，可补充 1-2 个细分关键词再搜一次。",
        ]
    elif len(relevant) >= 1:
        verdict = "warn"
        message = (
            f"⚠️ 偏少（领域：{domain}）：找到 {len(candidates)} 条候选，但真正相关的只有 {len(relevant)} 条，"
            "可能只能覆盖部分角度。"
        )
        suggestions = [
            "拆成 2 个对象对比（例如先做 A vs B，再单独看 C）。",
            "用单个产品名分别搜索，别把多个产品挤在一个关键词里。",
            "检查是否选到了媒体最近 1-2 周持续报道的细分话题。",
        ]
    else:
        verdict = "none"
        message = (
            f"❌ 没料（领域：{domain}）：现有白名单媒体（科技/金融向）近期基本不覆盖这个话题，"
            "跑完整分析大概率拿不到事实。"
        )
        suggestions = [
            "换更受媒体关注的选题（有热点的方向更容易抓到信息）。",
            "把 3 个对象对比拆成 2 个对象，成功率更高。",
            "用官方产品名（如「网易云音乐」而不是「网抑云」）重试。",
            "混合中英文复合词（如「豆包大模型」）会自动拆词检索，仍没料说明话题近期确实没报道。",
        ]
    domain_tips = {
        "科技": "科技类选题建议用「官方产品名+技术关键词」（如 豆包大模型、ChatGPT API 定价）。",
        "金融": "金融类选题建议带上具体指标词（财报/融资/估值/监管），财经源（第一财经/界面/21财经）覆盖更好。",
        "综合": "科技+金融混合选题，建议拆成两个角度分别搜。",
        "其他": "未识别到科技/金融领域词，可能是冷门或太泛的选题，建议换更具体的产品/公司名。",
    }
    suggestions.append(domain_tips[domain])

    if failed:
        message += f"（{len(failed)} 个来源暂不可用：{', '.join(failed)}）"
    return {
        "verdict": verdict,
        "domain": domain,
        "message": message,
        "candidates": top,
        "total": len(candidates),
        "relevant": len(relevant),
        "suggestions": suggestions,
        "failed": failed,
    }


def format_report(info: dict) -> str:
    """把预检结果格式化为 Markdown 文本（Web 与 CLI 通用）。"""
    lines = [info["message"], ""]
    if info["candidates"]:
        lines.append(f"相关候选（前 {len(info['candidates'])} 条）：")
        for i, c in enumerate(info["candidates"], start=1):
            lines.append(
                f"{i}. **{c['title']}**（来源：{c['source']}，相关度 {c['score']}）\n"
                f"   {c['url']}\n"
                f"   {c['date']}"
            )
    lines += ["", "建议："]
    lines += [f"- {s}" for s in info["suggestions"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="CrawlerAgent 选题助手：预检课题在白名单媒体的覆盖情况")
    parser.add_argument("--topic", required=True, help="分析课题或关键词，例如：豆包 通义千问")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    info = check_topic(args.topic, top_k=args.top_k)
    print(format_report(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())