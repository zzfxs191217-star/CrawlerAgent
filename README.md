# CrawlerAgent — 智能竞品情报分析 Agent

> 你只要输入一个公司名或产品名，它就会自动帮你完成：搜新闻 → 读文章 → 提炼要点 → 写出一份带引用来源的竞品分析报告。

## 这个项目是做什么的？

给完全没接触过编程的你解释：这是一个“会自己上网查资料的 AI 助手”。

平时做竞品分析，你需要自己打开很多网页，一篇篇复制粘贴、阅读、记笔记，最后手动整理成报告，非常耗时。CrawlerAgent 把这些全自动了——你只需要输入一个名字（比如“豆包”），它就会自己去可信的科技媒体上搜索相关新闻、抓取正文、理解内容，最后给你一份结构清晰的 Markdown 报告，**每条结论都带原始来源链接**，方便你核实。

## 它能帮你做什么？

- **竞品动态监控**：想知道“字节跳动的豆包”最近有什么新闻？输入名字，它帮你搜一圈并总结。
- **竞争态势分析**：输入“分析 XX 与 YY 的竞争态势”，它输出一份含资料清单、客观事实、SWOT 分析、结论与来源链接的完整报告。
- **长期记忆**：历史报告会自动存入知识库，下次分析会参考旧结论，越用越“懂行”。

## 效果示例

输入：
`分析字节跳动旗下豆包与阿里通义千问的竞争态势`

输出一份 Markdown 报告（保存在 `reports/` 目录），包含：
1. 资料清单（用了哪些新闻、链接在哪）
2. 客观事实（如“豆包月活 3.82 亿”），每条都标注来自哪篇文章
3. SWOT 分析（优势 / 劣势 / 机会 / 威胁）
4. 综合结论
5. 审查结果（AI 自查：每条结论是否都有原文依据）

## 工作原理

```
输入公司/产品名
   ↓ ① 搜索：在可信媒体白名单（钛媒体、爱范儿、极客公园、量子位…）的 RSS 里按关键词找新闻
   ↓ ② 抓取：抓取新闻正文（仅允许白名单域名，带浏览器标识模拟正常访问）
   ↓ ③ 提炼：研究员角色提取客观事实，不掺主观评价
   ↓ ④ 分析：分析师角色做 SWOT 与竞争态势分析
   ↓ ⑤ 成稿：审查员核对每条结论都有原文依据 → 生成带引用的 Markdown 报告 → 存入长期记忆
```

## 新手起步教程（约 15 分钟）

### 第一步：安装软件
1. 安装 **Python 3.10 或更高版本**：https://www.python.org/downloads/ （Windows 安装时勾选 “Add Python to PATH”）
2. 安装 **uv**（Python 包管理器，比传统 pip 快很多）：
   - Windows（在 PowerShell 里运行）：`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS / Linux：`curl -LsSf https://astral.sh/uv/install.sh | sh`

### 第二步：获取项目代码
- 方式 A（推荐，方便以后更新）：`git clone git@github.com:zzfxs191217-star/CrawlerAgent.git`
- 方式 B（新手最简单）：在 GitHub 仓库页面点绿色 **Code → Download ZIP**，解压到任意文件夹。

### 第三步：配置密钥（唯一需要你“动手”的地方）
1. 打开阿里云百炼控制台：https://bailian.console.aliyun.com/
2. 用阿里云账号登录，开通模型服务，创建一个 **API Key**（复制下来）
3. 进入项目根目录，把文件 `.env.example` **复制一份并改名为 `.env`**
4. 用记事本打开 `.env`，把密钥填进去：
   ```
   DASHSCOPE_API_KEY=这里填你的API Key
   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   ```
5. 保存文件。

### 第四步：安装依赖并验证
在项目根目录打开终端，运行：
```
uv sync
uv run python scripts/connectivity_test.py
```
如果看到模型返回一段自我介绍文字，说明环境配置成功。

### 第五步：跑第一个完整分析
- **新手推荐（Web 界面）**：运行 `uv run python -m crawler.webui`，浏览器打开 `http://127.0.0.1:7860`，输入课题点“开始分析”，3–5 分钟后在页面直接查看、下载，并可导出 PDF/Word（建议先用「选题助手」页签预检成功率）。
- 命令行方式：运行 `uv run python -m crawler.multi_agent.orchestration --topic "分析字节跳动旗下豆包与阿里通义千问的竞争态势"`，结束后到 `reports/` 文件夹里打开生成的 `.md` 文件。

## 常用命令速查

| 命令 | 作用 |
|---|---|
| `uv run python scripts/connectivity_test.py` | 连通性测试（验证密钥与网络） |
| `uv run python -m crawler.webui` | Web 界面（推荐新手，浏览器一键分析） |
| `uv run python -m crawler.agent.loop_v1` | 交互式智能体（可以连续追问） |
| `uv run python -m crawler.multi_agent.orchestration --topic "你的分析课题"` | 命令行一键生成完整分析报告 |
| `uv run python -m crawler.memory.store --index-reports` | 把历史报告加入长期记忆库 |
| `uv run python -m crawler.memory.store --query "检索问题"` | 检索长期记忆 |
| `uv run python -m crawler.export --file reports/报告.md --fmt pdf,docx` | 把报告导出为 PDF/Word |
| `uv run python -m crawler.topic_check --topic "课题"` | 选题预检：先看这个话题有没有料 |

## 项目结构（给想深入看代码的人）

```
CrawlerAgent/
├── .env.example          # 环境变量模板（复制为 .env 填入密钥）
├── crawler/
│   ├── config.py         # 读取配置
│   ├── sources.py        # 可信媒体白名单
│   ├── agent/            # 智能体主循环（V0.0 单工具 / V1.0 多步推理）
│   ├── tools/            # 智能体可调用的工具（抓网页/搜新闻/查记忆/取时间）
│   ├── memory/           # 长期记忆知识库（V3.0：向量化 + 检索）
│   ├── multi_agent/      # 多角色协作（V2.0：研究员/分析师/审查员）
│   └── webui.py          # Web 界面（V3.1：浏览器一键分析）
├── scripts/              # 辅助脚本（连通性测试等）
├── docs/                 # 规划书、决策记录
├── LICENSE               # MIT 开源协议
└── README.md
```

## 开发进度

- [x] V0.0 → V1.0 → V2.0 → V3.0 → V3.1 Web 界面 → V3.2 报告导出 PDF/Word
- 后续规划：定时监控、API 化（详见 `docs/decisions.md`）

## 选题技巧（提高成功率）

- **热点优先**：选最近 1-2 周媒体持续报道的方向，更容易抓到信息。
- **2 个对象对比**：先做 A vs B，别一次对比 3 个产品（例如 QQ音乐/网易云/汽水音乐容易失败）。
- **先预检再开跑**：用 Web 界面的「选题助手」页签，1 分钟就知道有没有料。
- 完整方法论见 `docs/topic_guide.md`。
## 常见问题（FAQ）

- **提示“请先配置 .env”？** → 密钥没配好，回到第三步检查。
- **提示密钥无效 / 额度不足？** → 到百炼控制台查看 Key 状态和免费额度。
- **某些网站抓不到内容？** → 只有白名单内的可信媒体才会被抓取，这是安全设计，不是 bug。
- **报告出现乱码？** → 确认 `.env` 用 UTF-8 编码保存（记事本另存为时选择）。
- **我的 API Key 会被别人看到吗？** → 不会。`.env` 已被 `.gitignore` 忽略，永远不会进仓库；但请勿把 `.env` 文件发给别人。

## 安全说明

- API 密钥只存本地 `.env`，不入库、不上传。
- 只从可信媒体白名单抓取内容，避免低质/不安全来源。
- 审查员角色会核对每条结论是否有原文依据，降低 AI 编造风险。
- 若密钥疑似泄露，立即到百炼控制台轮换新 Key。

## License

本项目基于 MIT 协议开源，可自由使用、修改与分发（详见 LICENSE 文件）。