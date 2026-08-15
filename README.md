# CrawlerAgent — 智能竞品情报分析 Agent

用户输入公司/产品名，自动完成：搜索新闻 → 抓取正文 → 深度提炼 → 输出带引用来源的 Markdown 竞争态势分析报告。

## 项目状态

- [x] 准备阶段：仓库骨架、项目记忆（AGENTS.md / docs/decisions.md）、无代理参考检索工具、国内网络检查
- [x] 阶段一：环境初始化 + 百炼连通性测试（M0 通过）
- [x] 阶段二（V0.0）：单工具调用闭环（M1 通过：抓取百度标题）
- [ ] 阶段三（V1.0）：ReAct 多步推理 + 工作台账记忆 + 用户可中断
- [ ] 阶段四（V2.0）：多角色协作 + 结构化报告

## 快速开始

1. `cp .env.example .env` 并填入百炼 API Key
2. `uv sync`
3. `uv run python scripts/connectivity_test.py`（连通性测试）
4. `uv run python -m crawler.agent.loop_v0`（V0.0 交互式工具调用）

## 文档

- 规划书：`docs/规划书-v1.0.md`
- 决策记录：`docs/decisions.md`
- 参考项目清单：`docs/references.md`
