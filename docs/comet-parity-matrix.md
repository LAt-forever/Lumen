# Comet 对标矩阵

日期：2026-06-30

本文档跟踪 Lumen 全面对标 Comet 的模块级进度。状态含义：

- `已具备`：Lumen 已有可用功能。
- `Phase 0`：本阶段交付运行底座或可见健康状态。
- `待实施`：已纳入总规格，后续阶段必须实现。
- `等价增强`：Lumen 以等价或更强方式覆盖 Comet 能力。

| Comet 模块族 | Lumen 当前状态 | 目标状态 | 阶段 |
| --- | --- | --- | --- |
| Docker 多服务运行栈 | PostgreSQL/Redis/backend/worker/frontend | 增加 Elasticsearch、Neo4j、beat 和完整健康检查 | Phase 0 |
| 运行健康状态 | 模型、资料、任务摘要 | PostgreSQL、Redis、Elasticsearch、Neo4j、worker、beat 全部可见 | Phase 0 |
| 多用户认证 | 已具备邮箱密码、JWT access token、bootstrap 用户、登录页和受保护路由 | Refresh/session 续期可作为后续增强 | 已具备 |
| 用户级数据隔离 | PostgreSQL 核心业务表、配置、Agent profile、worker job 和 ES source chunk projection 已按 user scope 隔离 | Neo4j 投影在 Phase 4 接入时继续继承 user scope | Phase 1 |
| 多知识库 | KnowledgeBase 模型、API、选择器、管理页、资料归属、图片库和摄取队列 scope 已完成 | 后续扩展到 Neo4j projection 和 Agent/Research 工作流 | Phase 3 完成 |
| ES 混合检索 | Elasticsearch source chunk projection、BM25/vector、RRF 混合排序、reranker hook、本地 fallback 和 remote embedding 后自动 projection 已完成 | 后续补充 analyzer 调优和可视化 rebuild 操作 | Phase 3 完成 |
| 真实 embedding | OpenAI-compatible embedding provider、profile 设置、测试接口和索引接线已完成；无配置时保留 hash fallback | 生产环境配置真实 provider/key 后启用 | Phase 2 完成 |
| 图片知识库 | 图片 OCR/vision parse、Image Library、asset 状态、搜索、聊天引用、标签和收藏已完成 | 后续可增强图片预览式引用卡和更强 vision provider 配置 | Phase 3 完成 |
| 文档知识库 | 多文件 parser、SourceAsset 元数据、详情页 parse/embedding/ES/graph 状态和可重试索引状态已完成 | 真实图谱同步进入 Phase 4 | Phase 3 完成 |
| Neo4j 记忆图谱 | 关系库存储和 React Flow 展示 | Neo4j 实体/关系/事件/provenance/time-line | Phase 4 |
| LLM 结构化记忆抽取 | 规则式候选抽取 | LLM 结构化抽取 + 用户确认 | Phase 4 |
| Agent 工具调用 | 受控只读工具 | ReAct/function-calling、工具注册、审批、日志 | Phase 5 |
| MCP 管理 | 无 | MCP server 配置、健康检查、工具发现 | Phase 5 |
| Skills | 无 | Skill CRUD、prompt template、工具权限 | Phase 5 |
| Research | 无 | planner/retriever/curator/distiller/report | Phase 6 |
| Persona | 无 | persona card、persona group、记忆策略 | Phase 7 |
| Group Chat | 无 | host orchestration、speaker prompt、join/share | Phase 7 |
| Dashboard | 今日/状态/回顾分散存在 | Comet 级 dashboard 聚合 | Phase 8 |
| Notifications | 无 | 站内、webhook、email-compatible provider | Phase 8 |
| Music | 无 | music library、lyrics、搜索、标签、收藏 | Phase 8 |
| Emotion | 无 | emotion records、抽取/手动录入、timeline | Phase 8 |
| Sharing | 无完整分享体系 | 会话、报告、知识摘要 tokenized read-only 分享 | Phase 8 |

## Phase 0 验收

- `docker compose up --build` 启动 PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、beat、frontend。
- 使用 bootstrap 用户登录后，带 `Authorization: Bearer <token>` 调用 `/api/status` 返回所有平台服务健康状态。
- 前端状态页显示所有平台服务。
- 现有资料摄取和聊天 smoke 流程保持可用。

## Phase 1 验收

- `/api/auth/login` 返回 JWT access token，`/api/auth/me` 返回当前用户。
- 未登录访问业务 API 返回 401。
- 前端无 token 时展示登录页，登录后进入工作台，并为 API 请求携带 Bearer token。
- sources、memories、conversations、ingestion jobs、tags、favorites、provider profiles、agent profiles、reranker profiles 和 tool logs 按当前用户隔离。
- worker 从 ingestion job 读取 `user_id` 并使用 scoped repositories。

## Phase 2 验收

- KnowledgeBase 支持创建、重命名、归档、恢复、删除空知识库，资料、摄取队列、搜索和聊天继承当前知识库范围。
- SourceChunk 和 IndexingRun 记录 user scope、knowledge base scope、embedding 状态和 index 状态。
- Provider profile 支持 embedding 能力字段和测试接口；active embedding profile 会用于新资料索引和 ES query embedding。
- Elasticsearch source chunk projection 支持 scoped BM25、vector kNN、RRF 混合排序、remote embedding 后自动写入和从 PostgreSQL scoped reload。
- `/api/search`、`/api/global-search` 和聊天引用路径已切到 RetrievalService，`auto` 模式在 ES 或 query embedding 失败时回退本地检索。
- 检索评测覆盖默认知识库隔离、ES BM25 精确关键词、vector 语义文本和弱证据 fallback。

## Phase 3 验收

- 上传图片会创建 SourceAsset，并展示文件名、MIME、大小、parse、embedding、ES index 和 graph 状态。
- 图片 parser 输出的 OCR/vision 文本会进入 source chunks；图片可通过搜索命中，也可在聊天回答中作为 citation 引用。
- remote embedding 成功后自动写入 Elasticsearch source chunk projection；ES 写入失败时 source/chunk/asset/indexing run 标记失败，local hash fallback 标记 skipped。
- Image Library 按当前用户和知识库 scope 只列出图片，并保留标签与收藏状态。
- Source Detail 展示 asset 元数据、索引运行、标签、收藏、失败可重试和网页资料刷新入口。
- 网页 link/bookmark/crawl source 可创建 refresh ingestion job，由 worker 重抓并重建索引。
- Graph 状态已在详情中展示为 Phase 3 状态面；真实 Neo4j projection 在 Phase 4 实现。
