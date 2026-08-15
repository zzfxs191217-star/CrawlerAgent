# 参考项目吸收笔记

日期：2026-08-15。来源：GitHub（无代理直连）。
结论先行：**借鉴思路与模式，不引入额外框架**（不采用 LangChain/LangGraph，保持 openai 兼容接口直连的轻量实现）。

## 1. antoinezambelli/forge（2.2k★，Python）
定位：自托管 LLM 工具调用的"可靠性层"，不是编排框架。
可借鉴：
- 工具调用护栏：解析失败救援（rescue parsing）、重试提示（retry nudge）、响应校验——直接应对"模型返回格式不标准"风险。
- 上下文压缩：ContextManager + TieredCompact 分层压缩历史对话——印证我们"分层摘要"设计；V1.0 可用 flash 模型压缩旧轮次。
- 可选流程约束：required_steps / prerequisites / terminal_tool——可映射到我们"搜索→抓取→摘要→报告"的阶段约束。
- 明确"不做多智能体编排"——我们的 V2.0 需要自己设计，参考 illufly 的 FlowAgent。

## 2. lhh737/LangChain-ReAct-Agent（319★，Python，中文）
定位：ReAct Agent + RAG + 工具调用 + Streamlit，最接近我们的 V1.0 形态。
可借鉴：
- ReAct 循环：Thought → Action → Observation，工具监控中间件，流式输出。
- 动态 System Prompt 切换：普通问答 vs 报告生成，按运行时上下文切换——对应我们各角色的提示词管理。
- YAML 驱动配置 + prompts/ 目录独立存放提示词模板——采用：把提示词外置到文件。
- RAG：Chroma + DashScope Embedding，MD5 去重——V3.0 直接参考。
- 不采用：LangChain/LangGraph 依赖，改为轻量直连实现。

## 3. modelstudioai/cli（304★，TypeScript，阿里云百炼官方）
定位：百炼官方 CLI，所有命令都可作为结构化工具调用。
要点：
- 百炼平台自带能力：内存管理（memory）、知识库检索（retrieval）、联网搜索（web search）——V3.0 可评估直接用平台能力替代自建向量库。
- 中国区账号可用 App 编排/知识库/记忆等；确认我们当前专属版 MaaS 端点属于国内体系。
- 后续对接百炼高级能力时，可参考其 CLI 的调用方式。

## 4. arcstep/illufly（80★，Python）
定位：基于"记忆蒸馏"的自我进化智能体，轻量框架。
可借鉴：
- FlowAgent 多智能体流：顺序节点 + Selector 条件分支/循环——对应 V2.0 研究员→分析师→审查员接力，以及"审查不过→打回分析师"的条件循环。
- 每节点独立 memory（system 提示词注入）——对应我们各角色独立 system prompt。
- 记忆蒸馏概念：把长对话压缩为紧凑记忆——印证"工作台账 + 摘要条目"方向。
- dotenv 最佳实践：.env 管理 APIKEY 与 BASE_URL。

## 后续可决策项
- V3.0：自建向量库（Chroma）还是直接用百炼平台知识库/记忆 API？届时再评估。
- 提示词外置：阶段二起把各角色/场景提示词放 prompts/ 目录。
- 是否需要 GitHub Token：本次未认证 API 检索遇到限流，但 raw.githubusercontent.com 抓文件不受限；暂时不需要用户提供 Token。