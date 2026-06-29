# Comet 对标矩阵

日期：2026-06-22

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
| 用户级数据隔离 | PostgreSQL 核心业务表、配置、Agent profile、worker job 已按 user scope 隔离 | ES/Neo4j 投影在 Phase 2/4 接入时继续继承 user scope | Phase 1 |
| 多知识库 | 无显式知识库 | KnowledgeBase 模型、选择器、资料归属 | Phase 2 |
| ES 混合检索 | hash embedding + 本地关键词 | Elasticsearch BM25/vector + rerank | Phase 2 |
| 真实 embedding | hash embedding | provider profile 驱动真实 embedding | Phase 2 |
| 图片知识库 | parser 已支持图片 OCR/vision 路径 | 图片库、搜索、引用、标签、收藏 | Phase 3 |
| 文档知识库 | 支持多文件 parser | 知识详情、asset 状态、可重试索引状态 | Phase 3 |
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
