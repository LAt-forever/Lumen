# Lumen 全面对标 Comet 计划设计

日期：2026-06-22

## 概要

Lumen 将从本地优先原型升级为 Comet 同级的个人 AI 知识库与 Agent 平台。目标是完整对标 Comet 开源仓库的能力范围，不因基础设施较重、多用户复杂、图数据库、检索成本、Agent 自主性或二级产品模块而打折扣。

这份规格取代早期“先做轻量原型”的长期边界。Lumen 已经做对的能力继续保留，并成为目标产品的核心气质：

- 有证据支撑的回答和可见引用。
- 显式可控的记忆确认、编辑、合并、遗忘和来源追踪。
- 持久摄取进度、失败修复和状态面板。
- 可审计的工具日志和受控配置。
- 中文优先的产品文案和日常使用体验。

新的目标形态补齐完整 Comet 级平台能力：

- 多用户认证和用户级数据隔离。
- 默认本地栈包含 PostgreSQL、Elasticsearch、Neo4j、Redis、Celery worker、Celery beat。
- 真实 embedding、混合检索、rerank 和可重建搜索索引。
- Neo4j 支撑的记忆图谱，包括实体、三元组、事件、来源、时间线和可视化。
- 多知识库、图片知识库、分享、标签、收藏、全局搜索、仪表盘和状态页。
- Agent 配置、工具、MCP server、Skills、研究任务、ReAct 或 function calling 执行和任务日志。
- Persona、Persona Group、群聊、通知、模型配置、音乐、情绪等 Comet 模块地图中的产品面。

## 产品决策

Lumen 不以 fork Comet 或复制 Comet 源码作为主路线。Lumen 会在现有代码库上演进到同一产品级别，同时保留本地代码所有权、已有测试和 Lumen 强调可信度的交互模型。

已确认的执行策略是：**演进式全量对标**。

1. 每个阶段结束后应用都必须可运行。
2. 先升级依赖的运行栈，再建设依赖该栈的功能。
3. 每个能力都按完整纵切交付：数据模型、服务层、API、worker 行为、前端入口、测试和 smoke 流程。
4. Comet 中用户可见的每个领域都纳入范围，除非未来经过用户明确批准调整范围。

## 对标定义

一个能力只有同时满足以下条件，才算完成对标：

- 用户可以在前端通过稳定路由或工作流访问。
- 后端提供持久 API 端点支撑该工作流。
- 数据持久化到正确存储，并带用户隔离。
- 异步流程有持久任务状态，并能在界面查看。
- 搜索、图谱和其他派生投影可以从主记录重建。
- 失败状态可见；适合重试的失败必须可重试。
- 测试覆盖核心服务行为和至少一条 API 路径。
- README 或阶段验收文档记录 smoke 流程。

## 目标

- 把 Lumen 做成 Comet 同级平台，而不是范围更窄的本地知识库原型。
- 采用完整多服务运行栈：PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、scheduler、frontend。
- 用真实 embedding、ES BM25/vector 检索和 rerank 替换 hash embedding 和关键词门控。
- 用 LLM 结构化记忆抽取替换规则式记忆抽取，同时保留用户确认机制。
- 用 Neo4j 支撑记忆图谱查询、可视化、社区式探索和时间线/事件推理。
- 加入完整多用户认证，以及关系库、搜索、图谱、文件和 worker 边界上的用户隔离。
- 补齐 Comet 级 Agent、MCP、Skills、研究、Persona、群聊、仪表盘、通知、模型配置、分享、图片、音乐和情绪模块。
- 继续把证据可见性、来源追踪、审批和审计日志作为 Lumen 的一等产品价值。

## 非目标

- 不把直接 fork Comet 作为主架构路线。
- 不为了速度引入隐藏的全局数据访问。
- 不接受绕过持久化、用户隔离或测试的 demo-only 功能。
- 不用静默自动化替代 Lumen 已有的记忆确认和可信控制。
- 在替代能力可用前，不移除现有 Lumen 工作流。

## 当前 Lumen 状态

Lumen 已经有可用底座：

- FastAPI 后端，使用 SQLAlchemy、Alembic、Celery、Redis，可配置 PostgreSQL，并保留 SQLite fallback。
- React 前端，使用 React Query、React Flow、d3-force，并已有中文工作台界面。
- 笔记、上传、链接、深度抓取、书签导入的持久摄取任务。
- 文本、Markdown、PDF、DOCX、EPUB、图片、网页链接、深度抓取、书签 HTML parser。
- 摘录式回答，以及配置后可用的 OpenAI-compatible LLM 回答；两者都带引用。
- 记忆候选、确认记忆、手动关系、图谱可视化、重复建议、标签、收藏、全局搜索、状态页、设置页和受控 Agent 工具。
- 检索评测 seed 命令和 smoke 指南。

当前关键限制：

- 检索仍使用 hash embedding 和进程内关键词/日期排序。
- 记忆抽取主要是确定性关键词分类。
- 记忆图谱存储在关系库，不在 Neo4j。
- Agent 只能运行预选只读工具，不具备自主多步规划。
- 没有多用户认证，也没有跨存储用户隔离。
- 默认 compose 栈没有 Elasticsearch 和 Neo4j。
- Persona、群聊、Skills、MCP 管理、研究、通知、音乐、情绪等产品模块缺失或不等价。

## 目标运行架构

默认开发和产品运行栈包含：

- `postgres`：用户、资料、会话、记忆元数据、模型配置、Agent 配置、任务、标签、收藏、分享、审计日志等事务型主数据库。
- `redis`：Celery broker、Celery result backend、短期缓存和协调原语。
- `elasticsearch`：全文、向量、混合检索和全局搜索索引。它应使用中文友好的 analyzer，并只保存可重建的搜索投影。
- `neo4j`：记忆图谱、实体图谱、三元组图谱、事件图谱、来源路径和图分析投影。
- `backend`：FastAPI API 服务。
- `worker`：Celery worker，处理摄取、embedding、索引、记忆抽取、图谱同步、研究、通知和重建任务。
- `beat`：Celery beat scheduler，处理周期性维护、重试、刷新和提醒类任务。
- `frontend`：React/Vite 前端。

SQLite 只作为历史兼容和窄范围开发检查的应急模式。Comet 对标目标栈不以 SQLite 为准。

## 数据所有权

PostgreSQL 是业务记录的主事实来源：

- 用户和认证记录。
- 知识库。
- 资料和文件元数据。
- 会话和消息。
- 记忆候选和记忆决策。
- 模型、provider、Agent、工具和 Skill 配置。
- 任务和审计日志。
- 标签、收藏、分享、通知和产品元数据。

Elasticsearch 是搜索投影：

- 资料 chunk。
- 图片描述和 OCR 文本。
- 会话和助手回答。
- 记忆和图谱派生摘要。
- 标签和收藏 boost 信号。
- 全局搜索文档。

Neo4j 是图查询投影：

- 记忆节点。
- 实体。
- 关系/三元组。
- 事件和时间锚点。
- 来源/消息 provenance 节点。
- 合并血统和矛盾/支持边。
- 用户和知识库范围属性。

投影重建是硬性要求。如果 Elasticsearch 或 Neo4j 数据丢失，worker 命令必须能从 PostgreSQL 和存储文件重建。

所有写入 Elasticsearch 和 Neo4j 的行为都必须经过服务边界或后台任务。Controller 不允许散落地直接双写多个存储。

## 多用户与隔离模型

每个用户拥有的数据表都必须拥有 `user_id`，或通过带 `user_id` 的父对象关联。范围包括 sources、chunks、ingestion jobs、conversations、messages、citations、memories、memory candidates、graph relations、tags、favorites、shares、model profiles、agent profiles、skills、MCP servers、research reports、notifications、image assets、music records 和 emotion records。

每个 Elasticsearch 文档必须包含：

- `user_id`
- `knowledge_base_id`，如果适用
- `document_type`
- `target_id`
- 可见性标记

每个 Neo4j 节点和关系必须包含：

- `user_id`
- `scope_type`
- `scope_id`
- 相关 provenance 字段

API handler 从认证上下文解析当前用户。Repository 方法要显式接收用户范围，或用用户范围对象构造。跨用户读取必须在 repository 或 service 边界被拒绝，不能只依赖 controller 过滤。

## 认证与账号

对标目标包括：

- 邮箱/密码登录。
- 由 settings 控制的注册开关。
- 密码哈希。
- JWT access token。
- Refresh token 或会话续期流程。
- 当前用户接口。
- 前端 auth store 和受保护路由。
- 登出。
- 由 settings 控制的管理员 bootstrap 用户。

Provider、reranker、模型、MCP、通知和外部工具配置中的 secret 字段继续加密存储。

## 知识库架构

Lumen 将加入显式多知识库支持。

核心对象：

- `KnowledgeBase`：用户拥有的文档、图片和网页捕获工作区。
- `Source`：一个原始资料记录。
- `SourceAsset`：存储文件或抓取原始 artifact。
- `SourceChunk`：解析后的文本 chunk，带 embedding 状态和索引状态。
- `IndexingRun`：embedding、ES 索引和图谱同步的持久记录。

摄取支持：

- 文本和 Markdown。
- PDF，支持 selectable text 提取和 OCR fallback。
- DOCX。
- EPUB。
- 图片 OCR 和 vision 描述。
- 网页链接。
- 递归网页抓取。
- 浏览器书签。
- 通过 parser registry 扩展未来文件类型。

知识库工作流：

- 创建、重命名、归档、删除知识库。
- 在聊天和搜索中选择当前知识库。
- 上传或捕获资料到一个或多个知识库。
- 查看资料详情、chunk、解析元数据、索引状态和引用记录。
- 重试失败的解析、embedding 和索引任务。
- 刷新网页资料和抓取任务。
- 分享指定会话、报告或资料摘要。

## 检索架构

Lumen 将用完整检索管线替换当前 hash embedding 检索。

管线：

1. 解析和切分资料内容。
2. 使用配置的 embedding provider 生成真实 embedding。
3. 在 PostgreSQL 存储 chunk 元数据和 embedding 状态。
4. 在 Elasticsearch 索引搜索投影，包含：
   - 正文。
   - 标题。
   - 标签。
   - 资料元数据。
   - 用户和知识库范围。
   - 向量字段。
   - 时间戳。
   - 引用指针。
5. 在一次请求或协调请求中查询 BM25 和向量检索。
6. 合并并归一化分数。
7. 配置 reranker 时执行 rerank。
8. 返回引用和匹配解释。

检索模式：

- 知识库搜索。
- 记忆搜索。
- 会话搜索。
- 图片搜索。
- 全局搜索。
- Agent 工具搜索。

评测命令要从小型 seed 扩展为版本化回归套件，衡量检索命中率、引用质量、弱证据行为和 reranker 改进。

## 记忆架构

记忆抽取升级为 LLM 结构化抽取，但确认机制继续显式存在。

抽取流程：

1. 用户消息、助手回答或资料 chunk 进入抽取候选输入。
2. worker 运行结构化抽取 prompt。
3. extractor 返回候选事实、偏好、项目、目标、关系、事件、实体和三元组。
4. 候选写入 PostgreSQL，带 provenance、confidence、原始模型输出和来源指针。
5. 用户可以确认、编辑、忽略、合并或遗忘候选。
6. 确认记忆写入 Neo4j 图谱投影。

Neo4j 图模型：

- `User`
- `Memory`
- `Entity`
- `Event`
- `Source`
- `Message`
- `KnowledgeBase`
- `Tag`

关系类型：

- `RELATED_TO`
- `BELONGS_TO`
- `CAUSES`
- `SUPPORTS`
- `CONTRADICTS`
- `MERGED_INTO`
- `MENTIONS`
- `DERIVED_FROM`
- `OCCURRED_ON`
- `PREFERS`
- `WORKS_ON`
- `HAS_GOAL`

每次图写入都必须带 provenance。图关系不能匿名存在。

记忆 UX：

- 待确认候选 inbox。
- 已确认记忆列表。
- 重复和冲突建议。
- 手动关系编辑器。
- 图谱视图。
- 时间线视图。
- provenance 路径检查器。
- 合并血统。
- 遗忘，以及策略允许时的恢复。

## Agent、工具、MCP 与 Skills

目标 Agent 系统要达到 Comet 的产品级别，同时保留 Lumen 的审计性。

核心对象：

- `AgentProfile`
- `AgentTool`
- `AgentTask`
- `AgentRun`
- `AgentStep`
- `AgentToolLog`
- `MCPServer`
- `Skill`
- `SkillVersion`

能力：

- 根据 provider 能力选择 ReAct loop 或 function-calling loop。
- 工具注册表覆盖知识搜索、记忆搜索、图谱查询、网页搜索、资料检查、报告创建、通知和 MCP 工具。
- MCP server 配置、健康检查和工具发现。
- Skills 支持 prompt template、说明和工具权限。
- Agent profile 级工具 allowlist。
- 写入类工具审批策略。
- 前端流式展示执行步骤。
- 持久 run log 和可回放 trace。

Agent 回答规则：

- 需要证据的任务必须引用检索资料或图谱 provenance。
- 写入动作必须通过策略检查；配置要求审批时必须等待审批。
- Agent 失败必须产生可见错误摘要和重试动作。

## 研究任务

Research 是一等 Agent 工作流，不是聊天附属能力。

工作流：

1. 用户创建研究任务，填写主题、范围、知识库选择和联网权限标记。
2. Planner 将任务拆解为研究问题。
3. Retriever 收集本地和外部证据。
4. Curator 过滤和聚类证据。
5. Distiller 写出结构化发现。
6. Report generator 生成带引用的已保存报告。
7. 用户可以分享报告。

研究 artifact 存在 PostgreSQL，可在 Elasticsearch 中搜索；当提取出记忆或实体声明时，要链接到图谱 provenance。

## Persona 与群聊

Lumen 将加入：

- persona cards。
- persona groups。
- group chat sessions。
- host 或 moderator 角色。
- 发言者选择。
- persona 专属 prompt。
- persona 记忆访问策略。
- 群聊分享和加入链接。

Persona chat 使用与单 Agent chat 相同的证据和记忆边界。Persona 不获得跨用户访问能力。

## 产品界面对标

前端路由将从当前 Lumen workbench 扩展为 Comet 级 app shell。

必须覆盖的路由族：

- Home 或 Dashboard。
- Chat。
- Knowledge Bases。
- Knowledge Detail。
- Image Library。
- Memory。
- Graph。
- Global Search。
- Favorites。
- Model Config。
- Agent Config。
- Agent Tasks。
- Research。
- Personas。
- Group Chat。
- Skills。
- MCP Tools。
- Notifications。
- Music Library。
- Emotion。
- Profile。
- Share pages。
- Status and maintenance。

前端可以保留 Lumen 当前更清晰的视觉风格，但功能面必须覆盖 Comet 模块地图。可以直接采用 Ant Design，也可以用等价组件达到 AntD 级覆盖；缺少必要控件不算对标。

## 仪表盘与状态页

Dashboard 对标包括：

- 最近知识变更。
- 最近记忆变更。
- 待确认记忆候选。
- 失败任务。
- 检索/索引健康。
- 图谱同步健康。
- PostgreSQL、Elasticsearch、Neo4j、Redis 和 worker 存储/服务健康。
- Agent task 状态。
- 最近会话。
- 收藏和标签。
- 建议下一步动作。

Status 对标包括：

- 任务队列。
- worker heartbeat。
- ES index health。
- Neo4j health。
- 投影重建动作。
- 失败 parse/index/graph-sync 重试。
- 维护命令文档。

## 标签、收藏与分享

标签和收藏升级为跨域基础能力：

- sources。
- chunks 或 documents。
- memories。
- messages。
- reports。
- images。
- music records。

标签建议可以来自确定性规则或 LLM，但确认必须可见。分享支持公开或 tokenized 的只读访问，用于会话、报告或指定知识摘要。

## 通知

通知渠道是用户拥有的配置。

初始渠道类型：

- 站内通知。
- webhook。
- email-compatible provider。

通知事件：

- 任务失败。
- 研究任务完成。
- 定期回顾就绪。
- 模型/provider 测试失败。
- 图谱或索引重建完成。
- Agent 需要审批。

## 音乐与情绪模块

音乐和情绪模块纳入对标范围，因为 Comet 将它们作为产品模块暴露。它们在知识、记忆和 Agent 核心能力之后实施，以复用用户隔离、文件存储、模型配置、标签、收藏和搜索。

音乐范围：

- track metadata。
- lyric storage。
- 标签和收藏。
- 搜索。
- 前端 library page。

情绪范围：

- mood 或 emotion records。
- 从会话抽取和手动录入。
- 时间线视图。
- 搜索和 dashboard 摘要。

## 模型与 Provider 配置

模型配置从当前聊天 provider profile 扩展为多能力 provider profile。

Provider profile 覆盖：

- chat completions。
- embeddings。
- vision。
- rerank。
- speech 或 audio 相关能力。
- 外部搜索 provider。

每个 profile 包含：

- provider type。
- base URL 或 provider-specific endpoint。
- model。
- 加密 secret 字段。
- timeout。
- test status。
- last error。
- user scope。
- 按能力区分的 active/default 标记。

运行时配置解析要选择能力专属 profile，而不是一个全局 chat profile。

## 后台任务

Celery worker 处理：

- 解析。
- OCR。
- vision 描述。
- embedding。
- Elasticsearch 索引。
- Neo4j 图谱同步。
- 记忆抽取。
- 重复和冲突检测。
- 研究任务步骤。
- 通知发送。
- 资料刷新。
- 投影重建。
- 清理。

Celery beat 调度：

- stale job recovery。
- 周期性健康快照。
- source refresh。
- reminder 和 review 生成。
- retry backoff 检查。

所有长流程都要把进度写入 PostgreSQL，并通过 API 暴露。

## API 形态

API 路由族：

- `/api/auth`
- `/api/users`
- `/api/knowledge-bases`
- `/api/sources`
- `/api/images`
- `/api/search`
- `/api/chat`
- `/api/memories`
- `/api/graph`
- `/api/tags`
- `/api/favorites`
- `/api/shares`
- `/api/model-profiles`
- `/api/agent-profiles`
- `/api/agent-tasks`
- `/api/tools`
- `/api/mcp`
- `/api/skills`
- `/api/research`
- `/api/personas`
- `/api/group-chat`
- `/api/notifications`
- `/api/music`
- `/api/emotions`
- `/api/status`
- `/api/maintenance`

现有 endpoint 可以暂时保留，但新的对标工作要逐步迁移到这些路由族。

## 迁移策略

迁移按阶段推进，并保持应用可运行。

1. 添加多服务 compose 和健康检查。
2. 添加用户模型和认证。
3. 给现有表添加 `user_id`，并回填 bootstrap local user。
4. 添加知识库模型，把现有 sources 分配到默认知识库。
5. 添加 Elasticsearch 投影服务和重建命令。
6. 添加真实 embedding provider profile，并迁移 chunk 索引到 ES。
7. 添加 Neo4j 投影服务和重建命令。
8. 添加 LLM 记忆抽取和图谱同步。
9. 扩展 Agent、Skills、MCP、研究、Persona 和产品模块。

数据迁移规则：

- 保留现有本地数据。
- 认证引入后，现有记录归属 bootstrap user。
- 重建命令必须幂等。
- 投影失败不能破坏 PostgreSQL 主记录。

## 项目阶段

### Phase 0：对标审计与运行底座

交付物：

- 仓库内 Comet 模块对标矩阵。
- Docker Compose 包含 PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、beat、frontend。
- 所有服务的健康 API。
- 环境和 README 更新。
- 服务健康聚合测试。

验收：

- `docker compose up --build` 启动完整栈。
- 状态页展示所有服务健康。
- 现有摄取和聊天 smoke 流程仍可运行。

### Phase 1：认证、用户与数据隔离

交付物：

- User model、auth API、JWT/session flow。
- 前端登录和受保护路由。
- 现有记录的 `user_id` 回填。
- Repository 级用户 scoping。
- 证明跨用户隔离的测试。

验收：

- 两个用户不能看到彼此的 sources、memories、conversations、jobs、tags 或 favorites。
- 现有本地数据分配给 bootstrap user。

### Phase 2：知识库与 Elasticsearch 检索

交付物：

- KnowledgeBase model 和 UI。
- ES index template 和 projection service。
- 真实 embedding provider profile。
- BM25/vector 混合检索。
- reranker 接入真实检索路径。
- 重建和 backfill 命令。

验收：

- 搜索和聊天通过 ES 检索。
- 评测套件输出命中指标。
- 删除 ES 数据后运行 rebuild 可以恢复搜索。

### Phase 3：图片与文档知识对标

交付物：

- Image library route。
- OCR 和 vision 索引管线。
- Source detail 扩展。
- 多知识库摄取。
- 文件 asset 元数据和可重试 parse/index 状态。

验收：

- 图片可以上传、描述、搜索、引用、打标签和收藏。
- 文档和图片失败状态可见且可重试。

### Phase 4：Neo4j 记忆图谱对标

交付物：

- Neo4j 连接、schema constraints 和 projection layer。
- 结构化 LLM 记忆抽取。
- 实体、关系、事件、来源和时间线图谱。
- 图谱重建命令。
- 基于 Neo4j 查询的图谱可视化。

验收：

- 确认记忆会创建图节点和关系。
- 图谱和时间线可以从 PostgreSQL 记录重建。
- 图谱 claim 的 provenance path 可见。

### Phase 5：Agent、MCP、Skills 与工具

交付物：

- Tool registry。
- MCP server 配置和发现。
- Skill CRUD 和 prompt template。
- Agent ReAct/function-calling loop。
- 写入类工具审批策略。
- 流式执行步骤和持久日志。

验收：

- Agent 可以搜索知识、查询记忆图谱、运行授权 MCP 工具，并产生带引用回答。
- 工具调用记录可见。
- 策略要求审批时，写入类工具必须等待审批。

### Phase 6：研究与报告

交付物：

- Research task model 和 UI。
- Planner、retriever、curator、distiller、report generator。
- 报告存储、搜索和分享。
- worker-backed 进度。

验收：

- 研究任务异步完成并生成带引用报告。
- 报告可以搜索和分享。

### Phase 7：Persona 与群聊

交付物：

- Persona profiles 和 persona groups。
- Group chat route。
- Host orchestration。
- Speaker prompts 和 persona memory policies。
- 加入/分享流程。

验收：

- 群聊可以运行多个 persona，并显示消息来源和用户范围上下文。

### Phase 8：Comet 产品面补齐

交付物：

- Dashboard 对标。
- Notifications。
- Music library。
- Emotion module。
- Profile 和 share pages。
- 最终路由和 README 对标矩阵。

验收：

- 每个 Comet 模块族都有 Lumen route、API、持久模型和 smoke 流程。
- README 不再把 Lumen 描述为本地原型。

## 测试策略

后端测试：

- repository 用户隔离。
- auth flow。
- ingestion jobs。
- ES projection 和 search service；必要时使用 fake 或 test ES adapter。
- Neo4j projection 和 graph service；必要时使用 fake 或 test adapter。
- memory extraction parser 和 confirmation flow。
- agent tool policy。
- research task state machine。
- rebuild commands。

前端测试：

- 受保护路由。
- 知识库选择。
- 搜索工作流。
- 记忆图谱工作流。
- Agent task panel。
- Research task panel。
- client state 的用户隔离。

集成和 smoke 测试：

- full compose health。
- 上传并索引资料。
- 带引用提问。
- 创建并确认记忆。
- 图谱同步。
- ES rebuild。
- Neo4j rebuild。
- Agent tool run。
- research report generation。

## 安全与隐私

- 所有用户数据都按认证用户隔离。
- Secret 加密存储。
- 日志脱敏常见 secret 形态。
- Agent 工具只接收权限允许的 scoped context。
- 分享链接是只读 tokenized 访问。
- 后台任务保存 user scope，并在修改记录前验证所有权。
- 重建命令需要显式 operator action 或 admin-scoped API 权限。

## 文档更新

每个阶段都要更新：

- README 能力列表。
- 环境设置。
- Docker Compose 服务列表。
- smoke 流程。
- 维护命令。
- 对标矩阵状态。

README 最终应把 Lumen 描述为完整 AI 知识和 Agent 平台，而不是本地优先原型。

## 阶段计划必须明确的决策

以下决策已在本计划中确定：

- Elasticsearch 和 Neo4j 是目标栈必需组件。
- 多用户认证是必需能力。
- Agent、MCP、Skills、研究、Persona、群聊、音乐、情绪、通知和分享都在范围内。
- 迁移必须保留现有 Lumen 数据。

以下实现选择必须在对应阶段计划里明确：

- 第一版生产 embedding provider。
- 直接采用 Ant Design，还是用现有组件体系达到等价覆盖。
- Neo4j constraint 语法和 index 名称。
- 本地 ES 镜像的 analyzer 配置。
- JWT refresh-token 存储策略。

## 成功标准

整个计划完成时必须满足：

- 一个 Docker Compose 命令启动完整栈。
- 多用户可同时使用应用且不发生数据泄露。
- 知识检索使用真实 embedding、ES 混合搜索和 reranking。
- 记忆抽取是 LLM 结构化抽取，并由 Neo4j 支撑图谱。
- Agent 能运行 MCP 和 Skills 支持的多步工具工作流。
- 研究任务能生成带引用报告。
- Persona 和群聊工作流可用。
- 图片、搜索、收藏、标签、分享、仪表盘、通知、音乐、情绪、模型配置、Profile 和状态页都存在。
- ES 和 Neo4j 投影重建可用。
- README 对标矩阵显示每个 Comet 模块族已经实现，或被 Lumen 等价/更强的工作流明确取代。
