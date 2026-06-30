# Lumen Comet Parity Phase 2 KnowledgeBase and ES Retrieval Design

更新日期：2026-06-29

## 背景

Phase 0 已把 PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、beat 和 frontend 纳入默认运行栈。Phase 1 已完成邮箱密码登录、JWT access token、bootstrap 用户、前端受保护工作台，以及 PostgreSQL 核心业务表和 worker job 的用户级隔离。

Phase 2 选择一次性完成知识库、真实 embedding、Elasticsearch BM25/vector 混合检索，并把搜索和聊天切换到新检索路径。这个阶段会触及数据模型、迁移、摄取、后台索引、检索、聊天、设置、前端知识库选择、评测和文档。

当前远端同步存在环境限制：无代理访问 GitHub 443 超时。Phase 2 设计基于本地 `codex/comet-parity-phase-1-auth-isolation` HEAD，该提交已经推送并由用户确认 PR 已合并。

## 目标

- 引入显式 `KnowledgeBase`，让每个用户拥有一个默认知识库，并允许创建、重命名、归档和删除空知识库。
- 将现有 `Source` 归属到知识库，所有资料列表、详情、摄取、搜索和聊天都继承 user scope 与 knowledge base scope。
- 扩展 provider profile，让配置可以声明 chat 和 embedding 能力；第一版真实 embedding 使用 OpenAI-compatible embeddings API。
- 将 `SourceChunk` 从单纯本地 hash embedding 记录升级为带 embedding/index 状态的 canonical chunk 元数据。
- 新增 Elasticsearch source chunk projection，支持 BM25、vector kNN、混合排序、重建和失败可见。
- 将 `/api/search`、`/api/chat`、`/api/chat/stream` 切换到新 retrieval service。
- 在 ES 或真实 embedding 不可用时可降级到现有本地检索，并把降级原因暴露到状态、日志或评测输出。
- 扩展前端，提供知识库选择器、知识库管理页和 embedding 配置入口。
- 扩展检索评测，覆盖知识库隔离、ES BM25、vector、混合排序、聊天引用和降级路径。

## 非目标

- 不在 Phase 2 实现 refresh token 或 session 续期；继续沿用 Phase 1 access token TTL 策略。
- 不实现图片库产品面、OCR/vision 重试 UI 或图片专属路由；图片资料仍作为 source 进入通用知识库。
- 不实现 Neo4j 图谱 projection；图谱 scope 在 Phase 4 处理。
- 不实现 Research、Persona、分享页、通知、音乐库或情绪模块。
- 不把 Elasticsearch 作为主事实源；ES 数据必须可从 PostgreSQL 和文件存储重建。
- 不强制要求真实 embedding 配置才能使用本地开发；无配置时可使用旧 hash/local 检索降级。

## 核心设计决定

### 1. PostgreSQL 是主事实源

`KnowledgeBase`、`Source`、`SourceChunk`、`IndexingRun` 和 provider profile 都以 PostgreSQL 为准。Elasticsearch 只保存可重建搜索投影。任何 API 返回用户数据时，都必须从 PostgreSQL 或 scoped repository 读取所有权边界。

### 2. 默认知识库接管历史资料

迁移会为每个用户创建一个名为 `默认知识库` 的 active knowledge base。现有 `sources.user_id` 为空的数据先归到 bootstrap user，再挂到该用户默认知识库；已有 `sources.user_id` 的资料挂到对应用户默认知识库。后续创建资料时，如果请求没有指定 `knowledge_base_id`，默认写入当前用户默认知识库。

### 3. 第一版 ES 只索引 source chunks

Phase 2 的 `/api/search` 和聊天知识引用只对 source chunks 使用 ES。全局搜索仍可以保留本地聚合路径，但其中的 source chunk 候选应复用新 retrieval service。memories、messages 后续可独立加入 ES projection，避免 Phase 2 同时重写过多横向模块。

### 4. Embedding profile 与 chat profile 共用表，能力分离

现有 `llm_provider_profiles` 已有加密 secret、active profile、状态测试等基础。Phase 2 在该表上增加：

- `supports_chat: bool`
- `supports_embedding: bool`
- `embedding_model: str | None`
- `embedding_dimensions: int | None`
- `embedding_status: untested | ready | failed`
- `embedding_last_error: str | None`
- `embedding_last_checked_at: datetime | None`

Chat 继续使用 active profile 的 chat 字段。Embedding 通过 `supports_embedding=True` 且 active 的 profile 解析；如果没有 active embedding profile，则 retrieval service 降级。

### 5. ES index 维度固定，由配置控制

Elasticsearch dense vector mapping 需要固定维度。第一版使用 `LUMEN_EMBEDDING_DIMENSIONS`，默认 `1536`。真实 embedding 返回维度必须与配置一致，否则该 indexing run 失败并记录错误。hash fallback 不写 ES vector；只用于本地降级检索。

### 6. Hybrid retrieval 使用可解释融合排序

BM25 和 vector 分别返回候选，retrieval service 以 rank reciprocal fusion 进行融合：

`score = bm25_weight / (rank + k) + vector_weight / (rank + k)`

默认 `bm25_weight=1.0`、`vector_weight=1.0`、`k=60`。结果继续填充 `ChunkRead`，保留 `matched_terms`、`matched_date`、`match_reason`，并追加模式说明，例如 `ES 混合检索：BM25 #2，vector #4`。

## 数据模型

### KnowledgeBase

新增表 `knowledge_bases`：

- `id`
- `user_id`
- `name`
- `description`
- `status`: `active | archived`
- `is_default`
- `created_at`
- `updated_at`

约束：

- `(user_id, name)` 唯一。
- 每个用户最多一个 `is_default=True` 的 active/default 记录。
- 删除仅允许空知识库；非空知识库只能归档。

### Source

扩展 `sources`：

- `knowledge_base_id`

查询 sources 时默认只返回当前用户当前知识库内资料；也支持显式 `knowledge_base_id` 参数。后台 retry/index 必须验证 source 属于当前用户或 job 所属用户。

### SourceChunk

扩展 `source_chunks`：

- `user_id`
- `knowledge_base_id`
- `content_hash`
- `token_count`
- `embedding_status`: `pending | embedded | failed | skipped`
- `embedding_provider_profile_id`
- `embedding_model`
- `embedding_dimensions`
- `embedding_error`
- `embedded_at`
- `index_status`: `pending | indexed | failed | skipped`
- `index_error`
- `indexed_at`
- `updated_at`

`SourceChunk` 继续保留 `embedding_json`，作为 PostgreSQL canonical 记录。真实 embedding 写入 JSON 并标记 `embedding_status=embedded`；无真实 embedding 时写入 hash/local embedding，标记 `embedding_status=skipped` 和 `index_status=skipped`，不得误报为 ES-ready。

### IndexingRun

新增表 `indexing_runs`：

- `id`
- `user_id`
- `knowledge_base_id`
- `source_id`
- `job_id`
- `run_type`: `source_index | rebuild | retry`
- `status`: `queued | running | succeeded | failed`
- `embedding_provider_profile_id`
- `embedding_model`
- `embedding_dimensions`
- `chunks_total`
- `chunks_embedded`
- `chunks_indexed`
- `error_message`
- `started_at`
- `finished_at`
- `created_at`
- `updated_at`

Indexing run 是长流程进度和失败可见的核心记录。worker index job 创建或更新 run；状态页和 source detail 可以读取它。

## API 设计

### Knowledge bases

新增 router：`/api/knowledge-bases`

- `GET /api/knowledge-bases`
- `POST /api/knowledge-bases`
- `PATCH /api/knowledge-bases/{id}`
- `POST /api/knowledge-bases/{id}/archive`
- `POST /api/knowledge-bases/{id}/restore`
- `DELETE /api/knowledge-bases/{id}`
- `POST /api/knowledge-bases/{id}/activate`

`activate` 不写入服务端 session，只返回当前知识库并由前端保存到 localStorage。后端所有写接口仍以请求参数为准；没有参数时使用默认知识库。

### Sources and ingestion

以下 API 增加可选 `knowledge_base_id`：

- `GET /api/sources`
- `POST /api/sources`
- `POST /api/sources/upload`
- `POST /api/sources/link`
- `POST /api/sources/crawl`
- `POST /api/sources/bookmarks`
- `POST /api/ingestion-jobs/notes`
- `POST /api/ingestion-jobs/uploads`
- `POST /api/ingestion-jobs/links`
- `POST /api/ingestion-jobs/crawls`
- `POST /api/ingestion-jobs/bookmarks`

`SourceRead` 增加 `knowledge_base_id` 和 `knowledge_base_name`。`IngestionJob` payload 保存 `knowledge_base_id`，worker 使用 job 的 user scope 和 knowledge base scope。

### Search and chat

- `GET /api/search?q=...&knowledge_base_id=...`
- `POST /api/chat` body 增加 `knowledge_base_id`
- `POST /api/chat/stream` body 增加 `knowledge_base_id`

未传 `knowledge_base_id` 时使用默认知识库。结果仍使用 `ChunkRead`、`ChatResponse` 和 `CitationRead`，新增字段应保持向后兼容，例如：

- `retrieval_mode`: `local | es_bm25 | es_vector | es_hybrid`
- `retrieval_source`: `elasticsearch | local_fallback`

Phase 2 必须在 `ChunkRead` 和 `CitationRead` 中增加这两个字段，前端以可选方式渲染，避免旧测试和旧调用路径被硬性破坏。

### Settings

Provider profile create/update 增加：

- `supports_chat`
- `supports_embedding`
- `embedding_model`
- `embedding_dimensions`

新增测试接口：

- `POST /api/settings/provider-profiles/{profile_id}/test-embedding`

测试成功会写 `embedding_status=ready`，失败会写脱敏错误。

## Embedding 设计

新增 `service.core.embeddings` 能力：

- 保留 `HashEmbeddingProvider` 用于本地降级和测试。
- 新增 `OpenAICompatibleEmbeddingProvider`。
- 新增 `EmbeddingProviderConfig`，由 settings 和 active embedding profile 解析。
- 新增 `build_embedding_provider(settings, profile)`。

OpenAI-compatible 请求：

- URL：`{base_url}/embeddings`，兼容 base_url 末尾是否包含 `/v1`。
- 请求体：`{"model": embedding_model, "input": [text1, text2, ...]}`
- 响应：读取 `data[*].embedding`。
- 超时：沿用 profile timeout。
- 错误：使用 `redact_text` 脱敏 api key、Authorization header 和 provider 返回内容。

批处理：

- 默认每批 32 chunks。
- 单批失败时 run 失败，source 标记 failed 或 index failed；已写入的 chunk embedding 保留，但 `index_status` 不能标记 indexed。

## Elasticsearch Projection 设计

索引名：

- 默认 alias：`lumen_source_chunks`
- 版本索引：`lumen_source_chunks_v1`

后端配置：

- `LUMEN_ELASTICSEARCH_URL`
- `LUMEN_ELASTICSEARCH_INDEX=lumen_source_chunks`
- `LUMEN_EMBEDDING_DIMENSIONS=1536`
- `LUMEN_RETRIEVAL_BACKEND=auto | elasticsearch | local`
- `LUMEN_RETRIEVAL_BM25_WEIGHT=1.0`
- `LUMEN_RETRIEVAL_VECTOR_WEIGHT=1.0`

文档 ID：

- `source_chunk:{chunk_id}`

ES 文档字段：

- `user_id`
- `knowledge_base_id`
- `source_id`
- `chunk_id`
- `source_title`
- `source_type`
- `text`
- `content_hash`
- `created_at`
- `updated_at`
- `embedding_model`
- `embedding_dimensions`
- `embedding`

Mapping：

- `text` 使用中文友好的 analyzer。第一版优先使用 ES built-in `standard` analyzer，避免强依赖未安装插件；如果本地环境有 IK analyzer，后续单独升级。
- `embedding` 使用 `dense_vector`，dims 来自 `LUMEN_EMBEDDING_DIMENSIONS`，启用 similarity `cosine`。
- scope 字段使用 keyword/integer filter。

Projection service：

- `ensure_index()`
- `index_chunk(chunk)`
- `delete_source(source_id)`
- `rebuild_knowledge_base(user_id, knowledge_base_id)`
- `search_bm25(query, scope, limit)`
- `search_vector(vector, scope, limit)`

所有 ES 写入只能从 projection service 或 worker 进入，controller 不直接双写 ES。

## Retrieval Service 设计

新增 `service.core.retrieval`：

输入：

- `user_id`
- `knowledge_base_id`
- `query`
- `limit`

流程：

1. 解析当前知识库 scope；缺省时使用默认知识库。
2. 判断 `LUMEN_RETRIEVAL_BACKEND`。
3. 如果 backend 为 `local`，直接走现有 KnowledgeService 本地检索。
4. 如果 backend 为 `auto` 或 `elasticsearch`：
   - 检查 ES 可用。
   - 检查 active embedding profile 可用。
   - 生成 query embedding。
   - 分别执行 BM25 和 vector 检索。
   - 使用 RRF 融合，按 chunk_id 去重。
   - 从 PostgreSQL 回读 chunk/source，防止 ES 返回越权或过期记录。
   - 组装 `ChunkRead`。
5. 如果 auto 模式下任一步失败，记录脱敏降级原因并走本地检索。
6. 如果 elasticsearch 强制模式失败，返回服务错误，便于生产环境发现配置问题。

Reranker：

- Phase 2 接入已有 active reranker profile 到 retrieval service 的最后一步。
- 如果 reranker 配置不完整或失败，auto 模式降级为未 rerank 的 hybrid 结果，并记录原因。
- Reranker 不改变 user/knowledge base scope，只能重排已 scoped 的候选。

## Chat 切换

`ChatOrchestrator` 不直接依赖 `KnowledgeService`，改为依赖 `RetrievalService` 或兼容接口：

- `search(query, limit, knowledge_base_id)`

`ChatRequest` 增加 `knowledge_base_id`。聊天引用只来自当前用户当前知识库的 source chunks。memory search 仍按用户级 scope，不按知识库过滤；如果后续需要 knowledge-base-scoped memory，在 Phase 4/6 另行设计。

Stream chat 使用相同 retrieval path，避免普通 chat 和 stream chat 结果不一致。

## 前端设计

### Knowledge base state

新增 `KnowledgeBaseContext`：

- 读取 `/api/knowledge-bases`。
- 默认选中 `is_default` 或 localStorage 保存的 knowledge base。
- 当保存的 knowledge base 不存在或 archived，回退默认知识库。
- 暴露 `activeKnowledgeBaseId`、`setActiveKnowledgeBaseId`、`knowledgeBases`。

### UI

导航新增“知识库”或在“资料库”顶部加入知识库切换器。第一版以工作台效率为优先：

- 侧边栏或 top bar 显示当前知识库 selector。
- Library view 增加知识库管理区域：创建、重命名、归档、恢复、删除空知识库。
- CapturePanel 的 note/upload/link/crawl/bookmark 提交带当前 `knowledge_base_id`。
- SearchPanel 查询带当前 `knowledge_base_id`。
- ChatPanel/CapturePanel 问答带当前 `knowledge_base_id`。
- SourceList 只显示当前知识库资料，并在空状态提示当前知识库名称。

视觉上保持当前工作台风格，不做营销页，不引入卡片套卡片。

### Settings

SettingsPanel 在模型配置处增加 embedding 能力字段：

- 支持聊天
- 支持 embedding
- embedding model
- embedding dimensions
- 测试 embedding

现有 LLM profile 列表需要显示 chat/embedding 能力和各自状态。

## Worker and Jobs

Index job 变更：

- job payload 保存 `knowledge_base_id`。
- worker 根据 job.user_id 构造 scoped repositories。
- parsing 成功后创建 chunks。
- embedding 成功后写 chunk embedding 元数据。
- ES indexing 成功后写 chunk index 状态。
- 任一步失败时写 `IndexingRun` 和 source/job 错误。

Rebuild：

- 新增后端命令或 API-internal service：按 user + knowledge base 重建 ES index。
- 重建先 ensure index，再批量读取 PostgreSQL chunks，重新写 ES。
- 删除 ES 数据后可以从 PostgreSQL 恢复。

## Error Handling

- ES 不可用：auto 模式降级 local；status 显示 degraded；强制 ES 模式返回错误。
- Embedding profile 未配置：auto 模式降级 local；settings/runtime 给出配置提示。
- Embedding 维度不匹配：indexing run failed，source index_status failed，不写 ES。
- ES 写入失败：chunk index_status failed，indexing run failed，source 保留 parsed/index failed 状态。
- Reranker 失败：auto 模式跳过 rerank 并记录原因。
- 跨用户或跨知识库访问：API 返回 404，不暴露目标是否存在。

## 测试策略

Backend：

- KnowledgeBase repository 用户隔离测试。
- 默认知识库 bootstrap 和历史 source 回填迁移测试。
- Source 创建、上传、link/crawl/bookmark 写入当前 knowledge base。
- Search API 按 knowledge base 过滤。
- Chat API 按 knowledge base 检索引用。
- Embedding provider OpenAI-compatible 请求/响应/错误脱敏测试。
- ES projection 使用 fake client 测试 ensure/index/delete/search。
- Retrieval service 测试 BM25/vector 融合、scope 回读、防越权、auto fallback、forced ES failure。
- Reranker 接入测试只允许 scoped candidates。
- Retrieval eval 覆盖 BM25、vector、hybrid、降级和聊天引用。

Frontend：

- Knowledge base selector 默认选择、切换和 localStorage 恢复。
- Library view 创建/重命名/归档/删除空知识库。
- Capture/search/chat 请求包含当前 `knowledge_base_id`。
- SettingsPanel embedding profile 字段和测试按钮。
- Status/Search/Chat 显示检索模式或降级提示。

Verification：

- `cd backend && uv run pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- 全新 SQLite Alembic upgrade head
- `docker compose config --services`
- Docker daemon 可用时跑完整 compose smoke：登录、创建知识库、摄取资料、ES 索引、搜索、聊天引用。

## 文档更新

- 更新 `README.md`：知识库、embedding profile、ES retrieval、降级行为和 smoke。
- 更新 `docs/comet-parity-matrix.md`：Phase 2 完成项。
- 更新 `docs/comet-parity-remaining-work.md`：Phase 2 checklist 和 Phase 3 下一步。
- 新增 implementation plan：`docs/superpowers/plans/2026-06-29-lumen-comet-parity-phase-2-knowledgebase-es-retrieval.md`。

## 分阶段执行策略

虽然 Phase 2 作为一次性交付合并，但实现按以下内部切片推进：

1. 模型、迁移、默认知识库和 source 归属。
2. KnowledgeBase API、repositories、schemas 和前端 selector。
3. Embedding profile 能力扩展与 OpenAI-compatible embedding provider。
4. SourceChunk indexing metadata、IndexingRun 和 worker index flow。
5. Elasticsearch projection service 和 rebuild service。
6. Retrieval service：BM25/vector/hybrid/local fallback/reranker。
7. Search/chat/stream 切换到 retrieval service。
8. Frontend knowledge base management、settings embedding UI 和检索提示。
9. Retrieval eval、README、对标文档和 smoke。

实现阶段建议启用 subagent-driven development，但不要并行派多个实现 subagent 修改代码。每个切片使用一个实现 subagent，然后依次进行 spec compliance review 和 code quality review。调研类任务可以并行，代码实现保持串行。

## 自检

- 范围覆盖：设计覆盖知识库、默认归属、真实 embedding、ES BM25/vector、混合排序、搜索/聊天切换、前端、评测和文档。
- 占位检查：本文没有未决占位。
- 数据边界：所有新增路径明确继承 user scope 和 knowledge base scope。
- 可恢复性：ES 明确为可重建 projection，PostgreSQL 仍为 canonical store。
- 风险控制：一次性交付被拆成串行可验证切片，降低跨模块冲突。
