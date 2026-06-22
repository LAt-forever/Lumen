# Lumen 全面对标 Comet Phase 0 运行底座实施计划

> **给 agentic workers：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务执行本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**目标：** 建设全面对标 Comet 的 Phase 0 底座：仓库内对标矩阵、包含 PostgreSQL/Redis/Elasticsearch/Neo4j/backend/worker/beat/frontend 的完整本地运行栈，以及用户可见的平台服务健康状态。

**架构：** PostgreSQL 继续作为事务型主事实来源；Elasticsearch 和 Neo4j 在本阶段作为必需平台服务接入，但暂不承担检索或图谱写入。后端通过现有 status API 暴露平台健康，Docker Compose 负责进程级健康检查，前端状态页展示服务健康，同时不改变现有摄取和聊天行为。

**技术栈：** FastAPI、SQLAlchemy、Celery、Redis、PostgreSQL、Elasticsearch 8、Neo4j 5、React、TanStack Query、Docker Compose、Pytest、Vitest。

---

## 范围检查

本计划只实现 `docs/superpowers/specs/2026-06-22-lumen-comet-parity-program-design.md` 中的 Phase 0。

包括：

- Comet 对标矩阵文档。
- Docker Compose 增加 Elasticsearch、Neo4j 和 Celery beat。
- 后端增加 ES、Neo4j、服务健康、beat heartbeat 设置。
- Status API 返回 service-health payload。
- Celery beat heartbeat 任务。
- 前端状态面板展示 service-health UI。
- README 增加 Phase 0 运行栈说明。
- 测试和验证命令。

不包括：

- Auth 和用户隔离。
- ES 索引与检索。
- Neo4j 图谱投影。
- Agent/MCP/Skills 实现。
- Research、persona、group chat、music、emotion、notification 工作流。

## 文件结构

- 新建 `docs/comet-parity-matrix.md`：权威 Comet 模块对标矩阵和 Phase 0 状态。
- 修改 `docker-compose.yml`：加入 Elasticsearch、Neo4j、beat 服务，并连接 backend/worker 依赖和环境变量。
- 修改 `backend/service/config.py`：加入 ES、Neo4j、service health 和 beat heartbeat 设置。
- 新建 `backend/service/core/service_health.py`：探测 PostgreSQL、Redis、Elasticsearch、Neo4j、Celery worker 和 beat heartbeat。
- 修改 `backend/service/core/status.py`：在状态摘要中加入服务健康。
- 修改 `backend/service/schemas.py`：加入服务健康 schema，并在 `StatusSummaryRead` 上加入 `services` 字段。
- 修改 `backend/service/worker.py`：加入 Celery beat heartbeat schedule 和 task。
- 修改 `backend/tests/test_status.py`：断言 status payload 包含服务健康，并保留现有 runtime 字段。
- 新建 `backend/tests/test_service_health.py`：不依赖真实 ES/Neo4j，单测服务探测成功/失败行为。
- 新建 `backend/tests/test_worker_heartbeat.py`：单测 heartbeat 文件写入。
- 修改 `frontend/src/api/types.ts`：加入 `ServiceHealthRead`，并在 `StatusSummaryRead` 上加入 `services`。
- 修改 `frontend/src/components/StatusPanel.tsx`：渲染服务健康卡片。
- 修改 `frontend/src/styles.css`：复用现有状态区样式，增加服务健康状态样式。
- 修改 `frontend/src/test/workbench.test.tsx`：mock `services` 并断言状态页渲染平台服务健康。
- 修改 `README.md`：记录 Phase 0 全栈、服务、健康检查和验收 smoke。

## 任务 1：添加 Comet 对标矩阵

**文件：**

- 新建：`docs/comet-parity-matrix.md`

- [ ] **步骤 1：写入对标矩阵文档**

创建 `docs/comet-parity-matrix.md`，内容如下：

```markdown
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
| 多用户认证 | 无 | 邮箱密码、JWT/session、受保护路由 | Phase 1 |
| 用户级数据隔离 | 无 | PostgreSQL/ES/Neo4j/文件/worker 全边界隔离 | Phase 1 |
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
- `/api/status` 返回所有平台服务健康状态。
- 前端状态页显示所有平台服务。
- 现有资料摄取和聊天 smoke 流程保持可用。
```

- [ ] **步骤 2：确认矩阵写明 Phase 0 必需服务**

运行：

```bash
rg -n "Elasticsearch|Neo4j|beat|Phase 0 验收" docs/comet-parity-matrix.md
```

期望：输出至少 4 行匹配结果，并包含 Phase 0 验收小节。

- [ ] **步骤 3：提交**

```bash
git add docs/comet-parity-matrix.md
git commit -m "docs: add Comet parity matrix"
```

## 任务 2：添加后端健康 schema 和设置

**文件：**

- 修改：`backend/service/config.py`
- 修改：`backend/service/schemas.py`
- 修改：`backend/tests/test_status.py`

- [ ] **步骤 1：编写失败的 status payload 测试**

把下面测试追加到 `backend/tests/test_status.py`：

```python
def test_status_summary_includes_platform_service_health(client, monkeypatch):
    from datetime import UTC, datetime

    from service.schemas import ServiceHealthRead

    def fake_collect_service_health(settings, db_session):
        return [
            ServiceHealthRead(
                name="postgres",
                label="PostgreSQL",
                status="ok",
                detail="SELECT 1 succeeded",
                latency_ms=1.2,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="redis",
                label="Redis",
                status="ok",
                detail="PING succeeded",
                latency_ms=2.3,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="elasticsearch",
                label="Elasticsearch",
                status="unavailable",
                detail="connection refused",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="neo4j",
                label="Neo4j",
                status="unavailable",
                detail="connection refused",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="worker",
                label="Celery Worker",
                status="unavailable",
                detail="no worker replied",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
            ServiceHealthRead(
                name="beat",
                label="Celery Beat",
                status="unavailable",
                detail="heartbeat file not found",
                latency_ms=None,
                checked_at=datetime(2026, 6, 22, tzinfo=UTC),
            ),
        ]

    monkeypatch.setattr("service.core.service_health.collect_service_health", fake_collect_service_health)

    response = client.get("/api/status")

    assert response.status_code == 200
    services = {item["name"]: item for item in response.json()["services"]}
    assert services["postgres"]["status"] == "ok"
    assert services["redis"]["label"] == "Redis"
    assert services["elasticsearch"]["status"] == "unavailable"
    assert services["neo4j"]["status"] == "unavailable"
    assert services["worker"]["detail"] == "no worker replied"
    assert services["beat"]["detail"] == "heartbeat file not found"
```

- [ ] **步骤 2：运行失败的后端测试**

运行：

```bash
cd backend
uv run pytest tests/test_status.py::test_status_summary_includes_platform_service_health -v
```

期望：失败，因为 `service.core.service_health` 或 `ServiceHealthRead` 尚不存在。

- [ ] **步骤 3：添加 settings 字段**

在 `backend/service/config.py` 的 `class Settings` 内、`playwright_enabled` 之后添加：

```python
    elasticsearch_url: str = "http://127.0.0.1:9200"
    neo4j_http_url: str = "http://127.0.0.1:7474"
    neo4j_bolt_url: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "lumen-password"
    service_health_timeout_seconds: float = 2.0
    beat_heartbeat_path: Path | None = None
    beat_heartbeat_max_age_seconds: int = 90
```

- [ ] **步骤 4：添加 service health schemas**

在 `backend/service/schemas.py` 现有 literal aliases 附近添加：

```python
ServiceHealthStatus = Literal["ok", "degraded", "unavailable", "not_configured"]
```

在 `StatusActionRead` 之前添加：

```python
class ServiceHealthRead(BaseModel):
    name: str
    label: str
    status: ServiceHealthStatus
    detail: str
    latency_ms: float | None = None
    checked_at: datetime
```

更新 `StatusSummaryRead`，加入 `services`：

```python
class StatusSummaryRead(BaseModel):
    runtime: RuntimeSettingsRead
    source_counts: SourceCountsRead
    ingestion_jobs: IngestionJobCountsRead = Field(default_factory=IngestionJobCountsRead)
    services: list[ServiceHealthRead] = Field(default_factory=list)
    failed_sources: list[FailedSourceRead] = Field(default_factory=list)
    pending_tag_suggestion_count: int
    latest_fallback_reason: str | None = None
    suggested_actions: list[StatusActionRead] = Field(default_factory=list)
```

- [ ] **步骤 5：运行 schema import 检查**

运行：

```bash
cd backend
uv run python -c "from service.config import Settings; from service.schemas import ServiceHealthRead, StatusSummaryRead; print(Settings().elasticsearch_url); print(ServiceHealthRead); print(StatusSummaryRead)"
```

期望：命令打印默认 Elasticsearch URL 和类名，不报错。

- [ ] **步骤 6：提交**

```bash
git add backend/service/config.py backend/service/schemas.py backend/tests/test_status.py
git commit -m "feat(status): define platform service health schema"
```

## 任务 3：实现服务健康收集

**文件：**

- 新建：`backend/service/core/service_health.py`
- 修改：`backend/service/core/status.py`
- 新建：`backend/tests/test_service_health.py`

- [ ] **步骤 1：编写 service health 单元测试**

创建 `backend/tests/test_service_health.py`：

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from service.config import Settings
from service.core.service_health import (
    check_beat_heartbeat,
    check_postgres,
    service_result,
)


def test_service_result_records_ok_latency():
    result = service_result(
        name="elasticsearch",
        label="Elasticsearch",
        started_at=10.0,
        finished_at=10.125,
        status="ok",
        detail="cluster green",
        checked_at=datetime(2026, 6, 22, tzinfo=UTC),
    )

    assert result.name == "elasticsearch"
    assert result.status == "ok"
    assert result.latency_ms == 125.0
    assert result.detail == "cluster green"


def test_check_postgres_reports_ok(client):
    from service.db import SessionLocal

    with SessionLocal() as db:
        assert db.execute(text("SELECT 1")).scalar() == 1
        result = check_postgres(db)

    assert result.name == "postgres"
    assert result.status == "ok"
    assert "SELECT 1" in result.detail


def test_check_beat_heartbeat_reports_missing_file(tmp_path):
    settings = Settings(beat_heartbeat_path=tmp_path / "missing.json")

    result = check_beat_heartbeat(settings)

    assert result.name == "beat"
    assert result.status == "unavailable"
    assert result.detail == "heartbeat file not found"


def test_check_beat_heartbeat_reports_stale_file(tmp_path):
    heartbeat = tmp_path / "beat-heartbeat.json"
    heartbeat.write_text('{"ok": true}', encoding="utf-8")
    stale_time = datetime.now(UTC) - timedelta(seconds=300)
    timestamp = stale_time.timestamp()
    heartbeat.touch()
    import os

    os.utime(heartbeat, (timestamp, timestamp))
    settings = Settings(beat_heartbeat_path=heartbeat, beat_heartbeat_max_age_seconds=30)

    result = check_beat_heartbeat(settings)

    assert result.name == "beat"
    assert result.status == "degraded"
    assert "heartbeat stale" in result.detail
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```bash
cd backend
uv run pytest tests/test_service_health.py -v
```

期望：失败，因为 `service.core.service_health` 尚不存在。

- [ ] **步骤 3：创建 service health 模块**

创建 `backend/service/core/service_health.py`：

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
from celery import Celery
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from service.config import Settings
from service.schemas import ServiceHealthRead, ServiceHealthStatus


def _now() -> datetime:
    return datetime.now(UTC)


def service_result(
    name: str,
    label: str,
    started_at: float,
    finished_at: float,
    status: ServiceHealthStatus,
    detail: str,
    checked_at: datetime | None = None,
) -> ServiceHealthRead:
    latency = round((finished_at - started_at) * 1000, 2)
    return ServiceHealthRead(
        name=name,
        label=label,
        status=status,
        detail=detail,
        latency_ms=latency,
        checked_at=checked_at or _now(),
    )


def unavailable(name: str, label: str, detail: str, started_at: float) -> ServiceHealthRead:
    finished_at = perf_counter()
    return service_result(
        name=name,
        label=label,
        started_at=started_at,
        finished_at=finished_at,
        status="unavailable",
        detail=detail,
    )


def check_postgres(db: Session) -> ServiceHealthRead:
    started_at = perf_counter()
    try:
        db.execute(text("SELECT 1")).scalar()
    except Exception as exc:
        return unavailable("postgres", "PostgreSQL", str(exc), started_at)
    return service_result(
        name="postgres",
        label="PostgreSQL",
        started_at=started_at,
        finished_at=perf_counter(),
        status="ok",
        detail="SELECT 1 succeeded",
    )


def check_redis(settings: Settings) -> ServiceHealthRead:
    started_at = perf_counter()
    try:
        Redis.from_url(settings.celery_broker_url, socket_timeout=settings.service_health_timeout_seconds).ping()
    except Exception as exc:
        return unavailable("redis", "Redis", str(exc), started_at)
    return service_result(
        name="redis",
        label="Redis",
        started_at=started_at,
        finished_at=perf_counter(),
        status="ok",
        detail="PING succeeded",
    )


def check_http_json(name: str, label: str, url: str, timeout_seconds: float) -> ServiceHealthRead:
    started_at = perf_counter()
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        detail = f"HTTP {response.status_code}"
    except Exception as exc:
        return unavailable(name, label, str(exc), started_at)
    return service_result(
        name=name,
        label=label,
        started_at=started_at,
        finished_at=perf_counter(),
        status="ok",
        detail=detail,
    )


def check_worker(settings: Settings) -> ServiceHealthRead:
    started_at = perf_counter()
    try:
        app = Celery("lumen-health", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
        replies = app.control.inspect(timeout=settings.service_health_timeout_seconds).ping() or {}
    except Exception as exc:
        return unavailable("worker", "Celery Worker", str(exc), started_at)
    if not replies:
        return service_result(
            name="worker",
            label="Celery Worker",
            started_at=started_at,
            finished_at=perf_counter(),
            status="unavailable",
            detail="no worker replied",
        )
    return service_result(
        name="worker",
        label="Celery Worker",
        started_at=started_at,
        finished_at=perf_counter(),
        status="ok",
        detail=f"{len(replies)} worker(s) replied",
    )


def _heartbeat_path(settings: Settings) -> Path:
    if settings.beat_heartbeat_path is not None:
        return settings.beat_heartbeat_path
    return settings.data_dir / "beat-heartbeat.json"


def check_beat_heartbeat(settings: Settings) -> ServiceHealthRead:
    started_at = perf_counter()
    path = _heartbeat_path(settings)
    if not path.exists():
        return service_result(
            name="beat",
            label="Celery Beat",
            started_at=started_at,
            finished_at=perf_counter(),
            status="unavailable",
            detail="heartbeat file not found",
        )
    age_seconds = datetime.now(UTC).timestamp() - path.stat().st_mtime
    if age_seconds > settings.beat_heartbeat_max_age_seconds:
        return service_result(
            name="beat",
            label="Celery Beat",
            started_at=started_at,
            finished_at=perf_counter(),
            status="degraded",
            detail=f"heartbeat stale: {int(age_seconds)}s old",
        )
    return service_result(
        name="beat",
        label="Celery Beat",
        started_at=started_at,
        finished_at=perf_counter(),
        status="ok",
        detail="heartbeat fresh",
    )


def collect_service_health(settings: Settings, db_session: Session) -> list[ServiceHealthRead]:
    elasticsearch_url = settings.elasticsearch_url.rstrip("/") + "/_cluster/health"
    return [
        check_postgres(db_session),
        check_redis(settings),
        check_http_json("elasticsearch", "Elasticsearch", elasticsearch_url, settings.service_health_timeout_seconds),
        check_http_json("neo4j", "Neo4j", settings.neo4j_http_url, settings.service_health_timeout_seconds),
        check_worker(settings),
        check_beat_heartbeat(settings),
    ]
```

- [ ] **步骤 4：接入 status service**

在 `backend/service/core/status.py` 添加 import：

```python
from service.core import service_health
```

在 `summary()` 中、`return StatusSummaryRead(...)` 之前添加：

```python
        services = service_health.collect_service_health(self.settings, self.sources.db)
```

然后在 `StatusSummaryRead(...)` 中加入：

```python
            services=services,
```

- [ ] **步骤 5：运行后端健康测试**

运行：

```bash
cd backend
uv run pytest tests/test_service_health.py tests/test_status.py::test_status_summary_includes_platform_service_health -v
```

期望：通过。

- [ ] **步骤 6：提交**

```bash
git add backend/service/core/service_health.py backend/service/core/status.py backend/tests/test_service_health.py
git commit -m "feat(status): collect platform service health"
```

## 任务 4：添加 Celery Beat heartbeat

**文件：**

- 修改：`backend/service/worker.py`
- 新建：`backend/tests/test_worker_heartbeat.py`

- [ ] **步骤 1：编写 heartbeat 测试**

创建 `backend/tests/test_worker_heartbeat.py`：

```python
import json


def test_record_beat_heartbeat_writes_configured_file(tmp_path, monkeypatch):
    heartbeat_path = tmp_path / "beat-heartbeat.json"
    monkeypatch.setenv("LUMEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LUMEN_BEAT_HEARTBEAT_PATH", str(heartbeat_path))

    from service.worker import record_beat_heartbeat

    record_beat_heartbeat()

    payload = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["service"] == "celery-beat"
    assert "recorded_at" in payload
```

- [ ] **步骤 2：运行测试确认失败**

运行：

```bash
cd backend
uv run pytest tests/test_worker_heartbeat.py -v
```

期望：失败，因为 `record_beat_heartbeat` 尚不存在。

- [ ] **步骤 3：实现 beat heartbeat task**

在 `backend/service/worker.py` 添加 imports：

```python
import json
from datetime import UTC, datetime
```

在 `celery_app.conf.update(...)` 之后添加：

```python
celery_app.conf.beat_schedule = {
    "lumen-beat-heartbeat": {
        "task": "service.worker.record_beat_heartbeat",
        "schedule": 30.0,
    }
}
```

在 `mark_stale_running_jobs_failed()` 之前添加 helper 和 task：

```python
def _beat_heartbeat_path() -> str:
    current_settings = Settings()
    path = current_settings.beat_heartbeat_path or (current_settings.data_dir / "beat-heartbeat.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@celery_app.task(name="service.worker.record_beat_heartbeat")
def record_beat_heartbeat() -> None:
    path = _beat_heartbeat_path()
    payload = {
        "ok": True,
        "service": "celery-beat",
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
```

- [ ] **步骤 4：运行 heartbeat 测试**

运行：

```bash
cd backend
uv run pytest tests/test_worker_heartbeat.py -v
```

期望：通过。

- [ ] **步骤 5：提交**

```bash
git add backend/service/worker.py backend/tests/test_worker_heartbeat.py
git commit -m "feat(worker): record celery beat heartbeat"
```

## 任务 5：扩展 Docker Compose 运行栈

**文件：**

- 修改：`docker-compose.yml`
- 修改：`.env.example`
- 修改：`backend/.env.example`

- [ ] **步骤 1：更新根目录环境示例**

在 `.env.example` 添加：

```dotenv
LUMEN_ELASTICSEARCH_URL=http://127.0.0.1:9200
LUMEN_NEO4J_HTTP_URL=http://127.0.0.1:7474
LUMEN_NEO4J_BOLT_URL=bolt://127.0.0.1:7687
LUMEN_NEO4J_USER=neo4j
LUMEN_NEO4J_PASSWORD=lumen-password
LUMEN_SERVICE_HEALTH_TIMEOUT_SECONDS=2
LUMEN_BEAT_HEARTBEAT_MAX_AGE_SECONDS=90
```

把同样内容也添加到 `backend/.env.example`。

- [ ] **步骤 2：在 Compose 中加入 Elasticsearch、Neo4j 和 beat**

用下面版本替换 `docker-compose.yml`，保留现有服务并增加新服务：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: lumen
      POSTGRES_USER: lumen
      POSTGRES_PASSWORD: lumen
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lumen -d lumen"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "6379:6379"

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.15.3
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms512m -Xmx512m"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://127.0.0.1:9200/_cluster/health >/dev/null"]
      interval: 10s
      timeout: 5s
      retries: 18
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/lumen-password
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 512m
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p lumen-password 'RETURN 1' >/dev/null"]
      interval: 10s
      timeout: 8s
      retries: 18
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j-data:/data
      - neo4j-logs:/logs

  backend:
    build:
      context: ./backend
    environment:
      LUMEN_DATABASE_URL: postgresql+psycopg://lumen:lumen@postgres:5432/lumen
      LUMEN_CELERY_BROKER_URL: redis://redis:6379/0
      LUMEN_CELERY_RESULT_BACKEND: redis://redis:6379/1
      LUMEN_ELASTICSEARCH_URL: http://elasticsearch:9200
      LUMEN_NEO4J_HTTP_URL: http://neo4j:7474
      LUMEN_NEO4J_BOLT_URL: bolt://neo4j:7687
      LUMEN_NEO4J_USER: neo4j
      LUMEN_NEO4J_PASSWORD: lumen-password
      LUMEN_DATA_DIR: /app/data
      LUMEN_UPLOAD_STORAGE_PATH: /app/data/uploads
      LUMEN_BEAT_HEARTBEAT_PATH: /app/data/beat-heartbeat.json
      LUMEN_LLM_MODE: extractive
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/healthz"]
      interval: 10s
      timeout: 5s
      retries: 12
    ports:
      - "8000:8000"
    volumes:
      - lumen-data:/app/data

  worker:
    build:
      context: ./backend
    command: ["uv", "run", "celery", "-A", "service.worker:celery_app", "worker", "--loglevel=info", "--concurrency=1"]
    environment:
      LUMEN_DATABASE_URL: postgresql+psycopg://lumen:lumen@postgres:5432/lumen
      LUMEN_CELERY_BROKER_URL: redis://redis:6379/0
      LUMEN_CELERY_RESULT_BACKEND: redis://redis:6379/1
      LUMEN_ELASTICSEARCH_URL: http://elasticsearch:9200
      LUMEN_NEO4J_HTTP_URL: http://neo4j:7474
      LUMEN_NEO4J_BOLT_URL: bolt://neo4j:7687
      LUMEN_NEO4J_USER: neo4j
      LUMEN_NEO4J_PASSWORD: lumen-password
      LUMEN_DATA_DIR: /app/data
      LUMEN_UPLOAD_STORAGE_PATH: /app/data/uploads
      LUMEN_BEAT_HEARTBEAT_PATH: /app/data/beat-heartbeat.json
      LUMEN_LLM_MODE: extractive
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    volumes:
      - lumen-data:/app/data

  beat:
    build:
      context: ./backend
    command: ["uv", "run", "celery", "-A", "service.worker:celery_app", "beat", "--loglevel=info", "--pidfile=/tmp/celerybeat.pid", "--schedule=/tmp/celerybeat-schedule"]
    environment:
      LUMEN_DATABASE_URL: postgresql+psycopg://lumen:lumen@postgres:5432/lumen
      LUMEN_CELERY_BROKER_URL: redis://redis:6379/0
      LUMEN_CELERY_RESULT_BACKEND: redis://redis:6379/1
      LUMEN_DATA_DIR: /app/data
      LUMEN_BEAT_HEARTBEAT_PATH: /app/data/beat-heartbeat.json
      LUMEN_LLM_MODE: extractive
    depends_on:
      redis:
        condition: service_healthy
      worker:
        condition: service_started
    healthcheck:
      test: ["CMD-SHELL", "test -f /tmp/celerybeat.pid"]
      interval: 10s
      timeout: 5s
      retries: 12
    volumes:
      - lumen-data:/app/data

  frontend:
    build:
      context: ./frontend
    environment:
      VITE_API_BASE: http://127.0.0.1:8000
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "5173:5173"

volumes:
  postgres-data:
  elasticsearch-data:
  neo4j-data:
  neo4j-logs:
  lumen-data:
```

- [ ] **步骤 3：校验 Compose config**

运行：

```bash
docker compose config >/tmp/lumen-compose-phase0.yml
rg -n "elasticsearch|neo4j|beat|LUMEN_ELASTICSEARCH_URL|LUMEN_NEO4J_HTTP_URL" /tmp/lumen-compose-phase0.yml
```

期望：输出包含新服务和新环境变量。

- [ ] **步骤 4：提交**

```bash
git add docker-compose.yml .env.example backend/.env.example
git commit -m "chore(compose): add ES Neo4j and beat services"
```

## 任务 6：在前端状态页渲染服务健康

**文件：**

- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/components/StatusPanel.tsx`
- 修改：`frontend/src/styles.css`
- 修改：`frontend/src/test/workbench.test.tsx`

- [ ] **步骤 1：更新前端测试 fixture**

在 `frontend/src/test/workbench.test.tsx` 中找到 mocked `/api/status` JSON response，加入下面的 `services` 数组：

```ts
services: [
  {
    name: 'postgres',
    label: 'PostgreSQL',
    status: 'ok',
    detail: 'SELECT 1 succeeded',
    latency_ms: 1.2,
    checked_at: '2026-06-22T00:00:00Z',
  },
  {
    name: 'redis',
    label: 'Redis',
    status: 'ok',
    detail: 'PING succeeded',
    latency_ms: 2.3,
    checked_at: '2026-06-22T00:00:00Z',
  },
  {
    name: 'elasticsearch',
    label: 'Elasticsearch',
    status: 'unavailable',
    detail: 'connection refused',
    latency_ms: null,
    checked_at: '2026-06-22T00:00:00Z',
  },
  {
    name: 'neo4j',
    label: 'Neo4j',
    status: 'unavailable',
    detail: 'connection refused',
    latency_ms: null,
    checked_at: '2026-06-22T00:00:00Z',
  },
  {
    name: 'worker',
    label: 'Celery Worker',
    status: 'unavailable',
    detail: 'no worker replied',
    latency_ms: null,
    checked_at: '2026-06-22T00:00:00Z',
  },
  {
    name: 'beat',
    label: 'Celery Beat',
    status: 'unavailable',
    detail: 'heartbeat file not found',
    latency_ms: null,
    checked_at: '2026-06-22T00:00:00Z',
  },
],
```

在状态页测试中、已有 `系统状态` 断言附近加入：

```ts
expect(await screen.findByText('平台服务')).toBeInTheDocument()
expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
expect(screen.getByText('Elasticsearch')).toBeInTheDocument()
expect(screen.getByText('Celery Beat')).toBeInTheDocument()
```

- [ ] **步骤 2：运行前端测试确认失败**

运行：

```bash
cd frontend
npm run test -- --runInBand src/test/workbench.test.tsx
```

期望：失败，因为尚未渲染 `平台服务`，或 TypeScript 类型尚未包含 `services`。

- [ ] **步骤 3：添加前端 service health 类型**

在 `frontend/src/api/types.ts` 中、`StatusSummaryRead` 之前添加：

```ts
export type ServiceHealthRead = {
  name: 'postgres' | 'redis' | 'elasticsearch' | 'neo4j' | 'worker' | 'beat' | string
  label: string
  status: 'ok' | 'degraded' | 'unavailable' | 'not_configured'
  detail: string
  latency_ms: number | null
  checked_at: string
}
```

然后在 `StatusSummaryRead` 上添加字段：

```ts
  services: ServiceHealthRead[]
```

- [ ] **步骤 4：渲染服务健康卡片**

在 `frontend/src/components/StatusPanel.tsx` 中，把下面 helper functions 加到 `StatusPanel` 上方：

```tsx
function serviceStatusLabel(status: string) {
  if (status === 'ok') return '正常'
  if (status === 'degraded') return '降级'
  if (status === 'not_configured') return '未配置'
  return '不可用'
}

function serviceStatusClass(status: string) {
  if (status === 'ok') return 'service-status ok'
  if (status === 'degraded') return 'service-status degraded'
  return 'service-status unavailable'
}
```

在现有 `status-grid` block 之后、`<IngestionProgressPanel mode="full" />` 之前插入：

```tsx
      <div className="platform-services">
        <div className="section-heading-row">
          <strong>平台服务</strong>
          <span>{status.services.length}</span>
        </div>
        <div className="service-health-grid">
          {status.services.map((service) => (
            <article className="service-health-card" key={service.name}>
              <div>
                <strong>{service.label}</strong>
                <p>{service.detail}</p>
              </div>
              <span className={serviceStatusClass(service.status)}>{serviceStatusLabel(service.status)}</span>
            </article>
          ))}
        </div>
      </div>
```

- [ ] **步骤 5：添加 CSS**

在 `frontend/src/styles.css` 中、现有 `.status-section` 规则附近添加：

```css
.platform-services {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-heading-row {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.service-health-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.service-health-card {
  align-items: flex-start;
  background: #ffffff;
  border: 1px solid #d8dee9;
  border-radius: 8px;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  min-height: 96px;
  padding: 14px;
}

.service-health-card p {
  color: #5f6b7a;
  font-size: 0.9rem;
  line-height: 1.4;
  margin: 6px 0 0;
  overflow-wrap: anywhere;
}

.service-status {
  border-radius: 999px;
  flex: 0 0 auto;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 4px 8px;
}

.service-status.ok {
  background: #e8f7ed;
  color: #1e7a3a;
}

.service-status.degraded {
  background: #fff4d6;
  color: #8a5a00;
}

.service-status.unavailable {
  background: #ffe4e4;
  color: #9f1d1d;
}
```

- [ ] **步骤 6：运行前端测试**

运行：

```bash
cd frontend
npm run test -- src/test/workbench.test.tsx
```

期望：通过。

- [ ] **步骤 7：提交**

```bash
git add frontend/src/api/types.ts frontend/src/components/StatusPanel.tsx frontend/src/styles.css frontend/src/test/workbench.test.tsx
git commit -m "feat(status): show platform service health"
```

## 任务 7：更新 README 的 Phase 0 运行栈说明

**文件：**

- 修改：`README.md`

- [ ] **步骤 1：更新服务列表**

在 `README.md` 中更新 Docker Compose 服务列表，包含：

```markdown
- 前端：http://127.0.0.1:5173/
- 后端：http://127.0.0.1:8000/
- Postgres：127.0.0.1:5432
- Redis：127.0.0.1:6379
- Elasticsearch：http://127.0.0.1:9200/
- Neo4j Browser：http://127.0.0.1:7474/，默认账号 `neo4j`，密码 `lumen-password`
```

- [ ] **步骤 2：添加 Phase 0 健康 smoke**

在现有 health check snippet 后添加：

````markdown
### Phase 0 全栈健康检查

全面对标 Comet 后，默认 Compose 栈会启动 PostgreSQL、Redis、Elasticsearch、Neo4j、backend、worker、beat 和 frontend。

```bash
docker compose ps
curl -s http://127.0.0.1:8000/api/status
```

期望：

- `docker compose ps` 中 `postgres`、`redis`、`elasticsearch`、`neo4j`、`backend`、`worker`、`beat`、`frontend` 均在运行。
- `/api/status` 的 `services` 字段包含 `postgres`、`redis`、`elasticsearch`、`neo4j`、`worker`、`beat`。
- 前端「状态」页展示「平台服务」卡片。
````

- [ ] **步骤 3：确认 README 提到所有服务**

运行：

```bash
rg -n "Elasticsearch|Neo4j|平台服务|beat" README.md
```

期望：输出包含新的 Phase 0 健康检查小节。

- [ ] **步骤 4：提交**

```bash
git add README.md
git commit -m "docs: document Phase 0 runtime stack"
```

## 任务 8：完整验证

**文件：**

- 无新增文件。

- [ ] **步骤 1：运行后端聚焦测试**

运行：

```bash
cd backend
uv run pytest tests/test_service_health.py tests/test_worker_heartbeat.py tests/test_status.py -v
```

期望：通过。

- [ ] **步骤 2：运行完整后端测试**

运行：

```bash
cd backend
uv run pytest -v
```

期望：通过。

- [ ] **步骤 3：运行前端测试**

运行：

```bash
cd frontend
npm run test
```

期望：通过。

- [ ] **步骤 4：构建前端**

运行：

```bash
cd frontend
npm run build
```

期望：通过，并在 `frontend/dist` 产生 Vite build 输出。

- [ ] **步骤 5：校验 Compose config**

运行：

```bash
docker compose config >/tmp/lumen-compose-phase0.yml
rg -n "elasticsearch|neo4j|beat|healthcheck" /tmp/lumen-compose-phase0.yml
```

期望：输出包含 Elasticsearch、Neo4j、beat 和 healthcheck 配置。

- [ ] **步骤 6：Docker 可用时运行完整 Compose smoke**

运行：

```bash
docker compose up --build
```

期望：

- PostgreSQL healthy。
- Redis healthy。
- Elasticsearch healthy。
- Neo4j healthy。
- Backend healthy。
- Worker 启动。
- Beat 启动，并通过 scheduled task 创建 heartbeat 文件。
- Frontend 在 `http://127.0.0.1:5173/` 启动。

在另一个 terminal 运行：

```bash
curl -s http://127.0.0.1:8000/api/status
```

期望：response 的 `services` 包含 `postgres`、`redis`、`elasticsearch`、`neo4j`、`worker` 和 `beat`。

- [ ] **步骤 7：最终状态检查**

运行：

```bash
git status --short
```

期望：工作树干净；如果 `.claude/` 这类用户原有无关文件已经存在，可以继续保留为未跟踪状态。

## 自审清单

- Spec 覆盖：实现 Phase 0 对标审计、运行栈、服务健康、状态页 UI 和文档。
- 文本完整性：计划正文没有未定项、临时标记或让执行者自行补全的步骤。
- 类型一致性：后端 `ServiceHealthRead` 字段与前端 `ServiceHealthRead` 一致。
- 范围控制：Phase 0 不做 auth、ES 检索、Neo4j 图写入、Agent、research、persona、music、emotion 或 notification feature work。
- 验证：包含后端测试、前端测试、前端 build、compose config，以及 Docker 可用时的完整 Compose smoke。
