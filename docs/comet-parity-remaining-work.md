# Comet 对标未完成事项追踪

更新日期：2026-06-29

本文档用于后续继续开发时快速判断“还没做什么”。继续推进 Comet 对标前，优先读取本文档，再按对应阶段去看详细规格和实施计划。

相关文档：

- `docs/comet-parity-matrix.md`
- `docs/superpowers/specs/2026-06-22-lumen-comet-parity-program-design.md`
- `docs/superpowers/plans/2026-06-22-lumen-comet-parity-phase-0-runtime-foundation.md`
- `docs/superpowers/plans/2026-06-29-lumen-comet-parity-phase-1-auth-isolation.md`

## 当前开发状态

- Phase 0 运行栈基础已落地，仍需在 Docker daemon 可用环境中完成完整 compose smoke。
- Phase 1 认证、用户与数据隔离已完成第一版实现，代码尚待提交和合并。
- 当前认证策略为邮箱密码登录 + JWT access token + bootstrap 用户 + 前端登出清理 token。
- refresh token 或 session 续期策略尚未实现，进入共享或生产环境前需要单独决策。
- 下一轮主线建议进入 Phase 2：知识库、多知识库归属、真实 embedding 和 Elasticsearch 混合检索。

## 当前已完成的基础

- 已完成 Comet 对标总规格和中文 Phase 0 计划。
- 已新增 `docs/comet-parity-matrix.md` 对标矩阵。
- Docker Compose 已加入 PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、beat、frontend。
- 后端 `/api/status` 已增加平台服务健康状态。
- 前端状态面板已展示平台服务健康。
- Celery beat heartbeat 已接入。
- Phase 1 已新增邮箱密码登录、JWT access token、bootstrap 用户、前端登录页和受保护工作台。
- 核心业务数据、模型配置、Agent 配置、reranker 配置和 worker job 已接入用户 scope。
- README、环境变量示例和 Docker Compose 环境变量已更新 Phase 0/Phase 1 说明。
- 后端、前端测试和前端构建已通过。

## 最新验证记录

2026-06-29 Phase 1 实现后已完成：

- `cd backend && uv run pytest`：192 passed, 1 skipped。
- `cd frontend && npm test -- --run`：25 passed。
- `cd frontend && npm run build`：通过。
- `cd backend && LUMEN_DATABASE_URL=sqlite:////private/tmp/lumen-phase1-alembic-final.db uv run alembic -c alembic.ini upgrade head`：通过。
- `docker compose config --services`：通过。
- `docker compose up --build -d`：未完成；本机 Docker daemon 未运行，错误为无法连接 `/Users/lanhezheng/.docker/run/docker.sock`。

## Phase 0 剩余收尾

- [ ] 确认 PR 已创建并合并到远端 `main`。
- [ ] 确认远端 `origin/main` 已包含 Phase 0 提交。
- [ ] 在 Docker daemon 可用的环境中运行 `docker compose up --build`。
- [ ] 用完整 compose 栈 smoke 验证：
  - [ ] PostgreSQL 正常。
  - [ ] Redis 正常。
  - [ ] Elasticsearch 正常。
  - [ ] Neo4j 正常。
  - [ ] backend 正常。
  - [ ] worker 正常。
  - [ ] beat heartbeat 正常。
  - [ ] frontend 正常。
- [ ] 在完整 compose 栈下验证资料摄取流程仍可用。
- [ ] 在完整 compose 栈下验证聊天和引用流程仍可用。

## Phase 1：认证、用户与数据隔离

目标：让 Lumen 从单用户本地应用升级为具备账号体系和用户级数据隔离的平台。

- [x] 新增用户模型。
- [x] 新增邮箱/密码登录。
- [x] 新增密码哈希。
- [x] 新增 JWT access token。
- [ ] 决定并实现 refresh token 或 session 续期策略；当前第一版使用 access token TTL + 客户端登出清除 token。
- [x] 新增当前用户接口。
- [x] 新增登出流程。
- [x] 新增注册开关。
- [x] 新增管理员 bootstrap 用户配置。
- [x] 前端新增登录页。
- [x] 前端新增 auth store。
- [x] 前端新增受保护路由。
- [x] 给现有用户数据表补 `user_id` 或等价用户归属关系。
- [x] 将现有本地数据回填到 bootstrap user。
- [x] Repository 层加入用户 scope。
- [x] Worker 任务保存并传递用户 scope。
- [x] 防止跨用户读取 sources、memories、conversations、jobs、tags、favorites。
- [x] 扩展隔离到 provider profiles、agent profiles、reranker profiles 和 tool logs。
- [x] 增加跨用户隔离测试。
- [x] 更新 README 和 smoke 文档。

## Phase 2：知识库与 Elasticsearch 检索

目标：引入多知识库、真实 embedding 和 ES 混合检索，替换当前 hash embedding 和本地关键词排序。

- [ ] 新增 KnowledgeBase 模型。
- [ ] 新增知识库创建、重命名、归档、删除 API。
- [ ] 前端新增知识库选择器和知识库页面。
- [ ] 将现有 sources 分配到默认知识库。
- [ ] 新增 SourceAsset、SourceChunk、IndexingRun 或等价索引状态模型。
- [ ] 扩展 provider profile，支持 embedding 能力。
- [ ] 决定第一版生产 embedding provider。
- [ ] 新增 Elasticsearch index template。
- [ ] 决定本地 ES 中文 analyzer 配置。
- [ ] 新增 ES projection service。
- [ ] 摄取完成后写入 ES 搜索投影。
- [ ] 实现 BM25 检索。
- [ ] 实现 vector 检索。
- [ ] 实现 BM25/vector 混合排序。
- [ ] 接入 reranker 到真实检索路径。
- [ ] 搜索和聊天改为使用 ES 检索。
- [ ] 新增 ES rebuild/backfill 命令。
- [ ] 删除 ES 数据后可从 PostgreSQL 和文件重建。
- [ ] 扩展检索评测套件，输出命中率和引用质量指标。

## Phase 3：图片与文档知识对标

目标：补齐 Comet 级图片库、文档详情、asset 状态和可重试索引体验。

- [ ] 新增 Image Library 路由。
- [ ] 图片上传后进入 OCR 和 vision 描述管线。
- [ ] 图片描述和 OCR 文本写入搜索投影。
- [ ] 图片可搜索。
- [ ] 图片可引用。
- [ ] 图片可打标签。
- [ ] 图片可收藏。
- [ ] 扩展 Source Detail 页面。
- [ ] 展示文件 asset 元数据。
- [ ] 展示 parse 状态。
- [ ] 展示 embedding 状态。
- [ ] 展示 ES index 状态。
- [ ] 展示图谱同步状态。
- [ ] parse/index 失败可见。
- [ ] parse/index 失败可重试。
- [ ] 支持多知识库摄取。
- [ ] 支持刷新网页资料和抓取任务。

## Phase 4：Neo4j 记忆图谱与结构化记忆

目标：把当前关系库图谱升级为 Neo4j 投影，并用 LLM 结构化抽取替换规则式记忆候选。

- [ ] 新增 Neo4j schema constraints。
- [ ] 新增 Neo4j projection layer。
- [ ] 确定 Neo4j constraint 和 index 命名。
- [ ] 确认记忆后写入 Neo4j。
- [ ] 图节点包含 user scope。
- [ ] 图关系包含 provenance。
- [ ] 支持实体节点。
- [ ] 支持关系和三元组。
- [ ] 支持事件节点。
- [ ] 支持来源路径。
- [ ] 支持时间线。
- [ ] 新增 Neo4j rebuild 命令。
- [ ] Neo4j 数据丢失后可从 PostgreSQL 重建。
- [ ] 新增 LLM 结构化记忆抽取。
- [ ] 抽取事实、偏好、项目、目标、关系、事件、实体和三元组。
- [ ] 保留用户确认、编辑、忽略、合并、遗忘流程。
- [ ] 前端图谱查询改为基于 Neo4j 或 Neo4j-backed service。
- [ ] 新增 provenance path 检查器。
- [ ] 新增时间线视图。
- [ ] 增加图谱和记忆抽取测试。

## Phase 5：Agent、MCP、Skills 与工具

目标：让 Agent 达到 Comet 产品级能力，同时保留 Lumen 的审批、引用和审计优势。

- [ ] 新增 Tool registry。
- [ ] 新增 AgentTool、AgentTask、AgentRun、AgentStep、AgentToolLog 等持久模型。
- [ ] Agent 支持 ReAct loop。
- [ ] Agent 支持 function-calling loop。
- [ ] 根据 provider 能力选择执行模式。
- [ ] 工具覆盖知识搜索。
- [ ] 工具覆盖记忆搜索。
- [ ] 工具覆盖图谱查询。
- [ ] 工具覆盖网页搜索。
- [ ] 工具覆盖资料检查。
- [ ] 工具覆盖报告创建。
- [ ] 工具覆盖通知。
- [ ] 新增 MCP server 配置。
- [ ] 新增 MCP server 健康检查。
- [ ] 新增 MCP 工具发现。
- [ ] 新增 Skill CRUD。
- [ ] 新增 SkillVersion。
- [ ] Skill 支持 prompt template。
- [ ] Skill 支持工具权限。
- [ ] Agent profile 支持工具 allowlist。
- [ ] 写入类工具支持审批策略。
- [ ] 前端流式展示 Agent 执行步骤。
- [ ] 持久化 run log。
- [ ] 可回放 trace。
- [ ] Agent 回答保留证据引用。
- [ ] Agent 失败产生可见错误摘要和重试动作。

## Phase 6：研究任务与报告

目标：把 Research 做成一等 Agent 工作流，而不是聊天附属功能。

- [ ] 新增 Research task model。
- [ ] 前端新增 Research 页面。
- [ ] 用户可填写主题、范围、知识库选择和联网权限。
- [ ] 实现 Planner。
- [ ] 实现 Retriever。
- [ ] 实现 Curator。
- [ ] 实现 Distiller。
- [ ] 实现 Report generator。
- [ ] 报告带引用。
- [ ] 报告持久化到 PostgreSQL。
- [ ] 报告可被 Elasticsearch 搜索。
- [ ] 报告可分享。
- [ ] 研究任务由 worker 异步执行。
- [ ] 前端展示研究任务进度。
- [ ] 研究中提取出的记忆或实体链接到图谱 provenance。

## Phase 7：Persona 与群聊

目标：补齐 Comet 的 persona、persona group 和 group chat 产品面。

- [ ] 新增 Persona profile。
- [ ] 新增 Persona group。
- [ ] 新增 Group chat session。
- [ ] 新增 host 或 moderator 角色。
- [ ] 新增发言者选择。
- [ ] Persona 支持专属 prompt。
- [ ] Persona 支持记忆访问策略。
- [ ] 群聊消息展示来源。
- [ ] 群聊遵守用户范围和知识库范围。
- [ ] 群聊支持分享。
- [ ] 群聊支持加入链接。
- [ ] Persona chat 使用与单 Agent chat 相同的证据和记忆边界。

## Phase 8：Comet 产品面补齐

目标：让每个 Comet 模块族都有 Lumen route、API、持久模型和 smoke 流程。

- [ ] Dashboard 对标。
- [ ] Dashboard 展示最近知识变更。
- [ ] Dashboard 展示最近记忆变更。
- [ ] Dashboard 展示待确认记忆候选。
- [ ] Dashboard 展示失败任务。
- [ ] Dashboard 展示检索和索引健康。
- [ ] Dashboard 展示图谱同步健康。
- [ ] Dashboard 展示 Agent task 状态。
- [ ] Dashboard 展示最近会话。
- [ ] Dashboard 展示收藏和标签。
- [ ] Dashboard 给出下一步建议。
- [ ] Notifications 模块。
- [ ] 站内通知。
- [ ] webhook 通知。
- [ ] email-compatible provider 通知。
- [ ] 通知事件覆盖任务失败、研究完成、定期回顾、provider 失败、重建完成、Agent 审批。
- [ ] Music Library。
- [ ] Track metadata。
- [ ] Lyric storage。
- [ ] 音乐搜索。
- [ ] 音乐标签和收藏。
- [ ] Emotion module。
- [ ] 情绪记录。
- [ ] 从会话抽取情绪。
- [ ] 手动录入情绪。
- [ ] 情绪时间线。
- [ ] 情绪搜索和 dashboard 摘要。
- [ ] Profile 页面。
- [ ] Share pages。
- [ ] Favorites 跨域升级。
- [ ] Tags 跨域升级。
- [ ] Status and maintenance 页面增强。
- [ ] README 最终更新为完整 AI 知识和 Agent 平台定位。
- [ ] 对标矩阵标记所有模块为已完成或等价增强。

## 横向未完成事项

- [ ] 所有新业务数据必须有用户隔离。
- [ ] 所有 secret 字段继续加密存储。
- [ ] 日志继续脱敏常见 secret。
- [ ] Agent 工具只能获得授权的 scoped context。
- [ ] 分享链接必须是只读 tokenized 访问。
- [ ] 后台任务修改记录前必须验证所有权。
- [ ] ES 和 Neo4j 投影必须可重建。
- [ ] 长流程必须写入 PostgreSQL 任务进度。
- [ ] 失败状态必须可见。
- [ ] 可重试失败必须提供重试动作。
- [ ] 每个阶段结束后更新 README。
- [ ] 每个阶段结束后更新 `docs/comet-parity-matrix.md`。
- [ ] 每个阶段结束后补 smoke 流程。
- [ ] 每个阶段必须有后端服务测试。
- [ ] 每个阶段至少覆盖一条 API 路径测试。
- [ ] 用户可见工作流要有前端测试或 smoke 验证。

## 下一步建议

下一步优先做 Phase 2：知识库与 Elasticsearch 检索。

原因：

- Phase 1 已经给 PostgreSQL 核心表、配置表和 worker job 建立用户边界。
- 后续 ES、Neo4j、Agent、MCP、Research、Persona 都应该继承当前 user scope 约定。
- Phase 2 是让当前资料检索从本地 hash/关键词路径升级到生产级知识库和 ES 混合检索的关键前置。
- 图片、图谱、Agent、Research 都依赖更稳定的 source/chunk/indexing 抽象。

进入 Phase 2 前建议先完成两个短收尾：

- 在 Docker daemon 可用环境中跑完整 compose smoke，包括登录、状态页、资料摄取、搜索和聊天引用。
- 决定 refresh token/session 续期是否要在 Phase 2 前补齐；如果只面向本地单机开发，可以暂缓。

Phase 2 开发前建议先写独立实施计划：

- `docs/superpowers/plans/YYYY-MM-DD-lumen-comet-parity-phase-2-knowledgebase-elasticsearch.md`

计划中必须明确：

- KnowledgeBase、SourceAsset、SourceChunk、IndexingRun 等模型边界。
- 默认知识库如何接管已有 sources。
- PostgreSQL canonical 数据与 Elasticsearch projection 的职责分工。
- embedding provider 选择和 provider profile 能力声明。
- ES index template、中文 analyzer、BM25/vector 混合排序和 reranker 接入方案。
- 摄取完成后如何异步写入 ES projection，并支持 rebuild/backfill。
- 搜索、聊天、引用路径如何继承 user scope 和 knowledge base scope。
- 检索评测指标、API 测试和前端 smoke 覆盖范围。
