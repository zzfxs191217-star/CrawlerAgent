# CrawlerAgent — 项目记忆与约定

本文件是 Codex 在本项目中的持久记忆，每次会话自动加载。修改需谨慎，重大变更请同步到 `docs/decisions.md`。

## 一、项目一句话

输入公司/产品名 → 自动搜索新闻 → 抓取正文 → 深度提炼 → 输出带引用来源的 Markdown 竞争态势分析报告。

## 二、技术栈（已确认）

- 语言：Python 3.10+（本机 Python 3.14）
- 依赖管理：uv（本机 0.12.4）；包源用清华 PyPI 镜像（全国内、无代理）
- LLM：阿里云百炼，OpenAI 兼容接口（`https://dashscope.aliyuncs.com/compatible-mode/v1`）
  - `qwen3.7-flash-2026-07-15`：高频机械活（摘要/提取/整理）
  - `qwen3.5-omni-plus-2026-03-15`：低频高质量活（规划/分析/成文/审查）
- 核心库：openai、python-dotenv、requests、beautifulsoup4
- 网络策略：所有外部端点国内可直达、不使用代理（见 `docs/decisions.md` D-006）

## 三、路线图（详见 `docs/规划书-v1.0.md`）

- 阶段一：环境初始化 + 百炼连通性测试（`scripts/connectivity_test.py`）
- 阶段二 V0.0：工具调用闭环（`crawler/tools/` + `crawler/agent/loop_v0.py`）
- 阶段三 V1.0：ReAct 多步推理 + 工作台账记忆 + 用户可中断（`crawler/agent/loop_v1.py`、`memory.py`）
- 阶段四 V2.0：研究员/分析师/审查员多角色协作 + Markdown 报告（`crawler/multi_agent/`）
- 阶段五 V3.0：长期记忆/知识库 RAG——分块向量化 + 检索工具 + 报告自动入库（`crawler/memory/`）

## 四、已确认的关键设计（决策详情见 `docs/decisions.md`）

1. 来源三层：发现层（白名单媒体 RSS 关键词检索，D-007）→ 内容层（白名单域名抓正文）→ 校验层（结论挂原文片段+URL）
2. 原始正文不进主对话：抓取 → 轻量摘要 → 结构化条目（URL/标题/日期/关键事实/可引用原句）
3. 工作台账 JSON 落盘 = 断点续跑（V1.0 实现）
4. 模型分层 + 每次调用记录 token 用量
5. 交互模式：阶段化 + 可中断（每阶段结束询问用户：继续/换方向/补充来源/跳过）
6. 上下文纪律：主循环只保留结构化条目 + 台账；原始网页和超长文本走单次摘要调用
7. 长期记忆（V3.0）：`crawler/memory/` 本地知识库，报告自动入库，智能体可用 `search_knowledge` 工具检索历史结论

## 五、工作约定

- 用户说“讨论/规划”时：只讨论，不创建代码或文件。
- 每个关键选型写入 `docs/decisions.md`（日期、背景、决策、理由）。
- API Key 只放 `.env`（不入库）；`.env.example` 放模板。
- `data/`（台账/轨迹）、`reports/`（报告）、`.venv/` 不入库。
- 每阶段结束有可验收产物；验收标准见规划书。
- 跨天继续项目时用 `codex resume` / `codex fork`。

## 六、常用命令

- `uv init` / `uv add <pkg>` / `uv run python <script>`
- 连通性测试：`uv run python scripts/connectivity_test.py`
- V1.0 智能体（交互）：`uv run python -m crawler.agent.loop_v1`
- V2.0 多角色报告：`uv run python -m crawler.multi_agent.orchestration --topic "分析课题"`
- 国内网络检查：`uv run python scripts/check_network.py`
- GitHub 参考检索：`uv run python scripts/gh_find.py 关键词`
- 记忆库入库：`uv run python -m crawler.memory.store --index-reports`
- 记忆库检索：`uv run python -m crawler.memory.store --query "问题"`
