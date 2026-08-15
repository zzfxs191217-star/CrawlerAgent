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
- 阶段六 V3.1：Web 界面（Gradio `crawler/webui.py`，CLI/Web 共用 `run_pipeline` 流水线）
- 阶段七 V3.2：报告导出 PDF/Word（`crawler/export.py`，CLI `--export` + Web 按钮）
- 阶段八 V3.3：选题助手——预检课题覆盖情况 + Web 页签 + 失败诊断（`crawler/topic_check.py`、`docs/topic_guide.md`）

## 四、已确认的关键设计（决策详情见 `docs/decisions.md`）

1. 来源三层：发现层（白名单媒体 RSS 关键词检索，D-007）→ 内容层（白名单域名抓正文）→ 校验层（结论挂原文片段+URL）
2. 原始正文不进主对话：抓取 → 轻量摘要 → 结构化条目（URL/标题/日期/关键事实/可引用原句）
3. 工作台账 JSON 落盘 = 断点续跑（V1.0 实现）
4. 模型分层 + 每次调用记录 token 用量
5. 交互模式：阶段化 + 可中断（每阶段结束询问用户：继续/换方向/补充来源/跳过）
6. 上下文纪律：主循环只保留结构化条目 + 台账；原始网页和超长文本走单次摘要调用
7. 长期记忆（V3.0）：`crawler/memory/` 本地知识库，报告自动入库，智能体可用 `search_knowledge` 工具检索历史结论
8. Web 界面（V3.1）：`crawler/webui.py` 本地服务（127.0.0.1:7860），密钥只留服务端；`run_pipeline` 支持进度回调与取消（`PipelineCancelled`），界面含取消任务/下载报告/模型选择
9. 报告导出（V3.2）：`crawler/export.py` 把 Markdown 报告渲染为 PDF（reportlab，中文字体回退 STSong-Light）与 Word（python-docx），CLI `--export` + Web 界面按钮
10. 验收修复（V3.2，D-012）：正文抽取优先内容容器；表格单元格 `|` 转义全角；PDF 表格行归一化+等分列宽；RSS 候选按相关度打分排序
11. 选题助手（V3.3，D-013）：`topic_check.py` 实体词提取 + 相关度判定（排除通用词/母公司噪音）；Web「选题助手」页签；`run_pipeline` 失败时输出诊断建议
12. 数据源（科技+金融，D-014/D-016）：发现层 RSS——钛媒体/爱范儿/极客公园/量子位/少数派/开源中国/cnBeta/InfoQ中文/雷锋网/新智元/IT之家/Solidot；列表页——第一财经/界面新闻/21财经；已实测不可用不接入（机器之心付费、亿欧 202、DoNews/品玩 404、晚点 SSL、华尔街见闻前端渲染、36氪/虎嗅反爬）；文娱源（机核/娱乐资本论/品牌星球）已按 D-016 移除
13. 列表页发现（D-015/D-016）：`search.py` `_match_list_page` 从 `sources.LIST_PAGES` 抓首页提取标题（支持 `title_selectors` / `title_attr`，按 URL 去重）
14. 科技+金融细化（D-017）：`search.py` 实体拆词（强词/弱词 + 已知领域词切分）、领域判定 `domain_of`、打分细化（2-gram 封顶 1.0、日期衰减 7d×1.2/30d×1.0/更早×0.5、金融源 +0.5）；选题助手输出领域与针对性建议
15. 领域词表文件化（D-018/D-019）：词表在 `config/domain_terms.json`（科技/金融→子类→词:权重 2强/1弱），`search.py` 启动加载、缺失回退内置精简表；强词参与拆词、弱词只做领域判定；`scripts/scan_domain_terms.py`（jieba+log 比率）生成候选到 `docs/domain_terms_candidates.md`，人工审核后并入，不自动入库；词表现状：科技 55 / 金融 48（含智能体生态词 多智能体/MCP/Copilot/Agentic 等）

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
- Web 界面：`uv run python -m crawler.webui`（浏览器打开 http://127.0.0.1:7860）
- 报告导出：`uv run python -m crawler.export --file reports/xx.md --fmt pdf,docx`
- 选题预检：`uv run python -m crawler.topic_check --topic "课题"`
- 领域词候选生成：`uv run python scripts/scan_domain_terms.py --per-source 80`（产出 `docs/domain_terms_candidates.md`，人工审核后并入 `config/domain_terms.json`）
