# Lumen Comet Parity Phase 0 Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 0 foundation for full Comet parity: a documented parity matrix, a complete local runtime stack with PostgreSQL/Redis/Elasticsearch/Neo4j/backend/worker/beat/frontend, and user-visible service health.

**Architecture:** PostgreSQL remains the transactional source of truth while Elasticsearch and Neo4j are introduced as required platform services but not yet used for retrieval or graph writes. The backend exposes platform health through the existing status API, Docker Compose owns process-level health checks, and the frontend status page renders service health without changing ingestion or chat behavior.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL, Elasticsearch 8, Neo4j 5, React, TanStack Query, Docker Compose, Pytest, Vitest.

---

## Scope Check

This plan implements only Phase 0 from `docs/superpowers/specs/2026-06-22-lumen-comet-parity-program-design.md`.

Included:

- Comet parity matrix documentation.
- Compose services for Elasticsearch, Neo4j, and Celery beat.
- Backend settings for ES/Neo4j/beat health.
- Status API service-health payload.
- Celery beat heartbeat task.
- Frontend status panel service-health UI.
- README Phase 0 runtime updates.
- Tests and verification commands.

Excluded from Phase 0:

- Auth and user isolation.
- ES indexing and retrieval.
- Neo4j graph projection.
- Agent/MCP/Skills implementation.
- Research, persona, group chat, music, emotion, notification workflows.

## File Structure

- Create `docs/comet-parity-matrix.md`: authoritative Comet module parity matrix and Phase 0 status.
- Modify `docker-compose.yml`: add Elasticsearch, Neo4j, and beat services; wire backend/worker dependencies and env vars.
- Modify `backend/service/config.py`: add ES, Neo4j, service health, and beat heartbeat settings.
- Create `backend/service/core/service_health.py`: probe PostgreSQL, Redis, Elasticsearch, Neo4j, Celery worker, and beat heartbeat.
- Modify `backend/service/core/status.py`: include service health in status summary.
- Modify `backend/service/schemas.py`: add service health schemas and `services` field on `StatusSummaryRead`.
- Modify `backend/service/worker.py`: add Celery beat heartbeat schedule and task.
- Modify `backend/tests/test_status.py`: assert status payload includes service health and preserves existing runtime fields.
- Create `backend/tests/test_service_health.py`: unit-test service probe success/failure behavior without real ES/Neo4j.
- Create `backend/tests/test_worker_heartbeat.py`: unit-test heartbeat file writing.
- Modify `frontend/src/api/types.ts`: add `ServiceHealthRead` and `services` on `StatusSummaryRead`.
- Modify `frontend/src/components/StatusPanel.tsx`: render service health cards.
- Modify `frontend/src/styles.css`: add service health status styles using existing status section patterns.
- Modify `frontend/src/test/workbench.test.tsx`: mock `services` and assert status page renders platform service health.
- Modify `README.md`: document Phase 0 full stack, services, health checks, and acceptance smoke.

## Task 1: Add Comet Parity Matrix

**Files:**

- Create: `docs/comet-parity-matrix.md`

- [ ] **Step 1: Write the parity matrix document**

Create `docs/comet-parity-matrix.md` with this content:

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

- [ ] **Step 2: Verify the matrix names required Phase 0 services**

Run:

```bash
rg -n "Elasticsearch|Neo4j|beat|Phase 0 验收" docs/comet-parity-matrix.md
```

Expected: four or more matching lines, including the Phase 0 acceptance section.

- [ ] **Step 3: Commit**

```bash
git add docs/comet-parity-matrix.md
git commit -m "docs: add Comet parity matrix"
```

## Task 2: Add Backend Health Schemas And Settings

**Files:**

- Modify: `backend/service/config.py`
- Modify: `backend/service/schemas.py`
- Modify: `backend/tests/test_status.py`

- [ ] **Step 1: Write failing status payload test**

Append this test to `backend/tests/test_status.py`:

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

- [ ] **Step 2: Run the failing backend test**

Run:

```bash
cd backend
uv run pytest tests/test_status.py::test_status_summary_includes_platform_service_health -v
```

Expected: FAIL because `service.core.service_health` or `ServiceHealthRead` does not exist.

- [ ] **Step 3: Add settings fields**

In `backend/service/config.py`, add these fields inside `class Settings` after `playwright_enabled`:

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

- [ ] **Step 4: Add service health schemas**

In `backend/service/schemas.py`, add this literal near the existing literal aliases:

```python
ServiceHealthStatus = Literal["ok", "degraded", "unavailable", "not_configured"]
```

Add this model before `StatusActionRead`:

```python
class ServiceHealthRead(BaseModel):
    name: str
    label: str
    status: ServiceHealthStatus
    detail: str
    latency_ms: float | None = None
    checked_at: datetime
```

Update `StatusSummaryRead` to include `services`:

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

- [ ] **Step 5: Run schema import check**

Run:

```bash
cd backend
uv run python -c "from service.config import Settings; from service.schemas import ServiceHealthRead, StatusSummaryRead; print(Settings().elasticsearch_url); print(ServiceHealthRead); print(StatusSummaryRead)"
```

Expected: command prints the default Elasticsearch URL and class names without errors.

- [ ] **Step 6: Commit**

```bash
git add backend/service/config.py backend/service/schemas.py backend/tests/test_status.py
git commit -m "feat(status): define platform service health schema"
```

## Task 3: Implement Service Health Collection

**Files:**

- Create: `backend/service/core/service_health.py`
- Modify: `backend/service/core/status.py`
- Create: `backend/tests/test_service_health.py`

- [ ] **Step 1: Write service health unit tests**

Create `backend/tests/test_service_health.py`:

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

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/test_service_health.py -v
```

Expected: FAIL because `service.core.service_health` does not exist.

- [ ] **Step 3: Create service health module**

Create `backend/service/core/service_health.py`:

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

- [ ] **Step 4: Wire status service**

In `backend/service/core/status.py`, add this import:

```python
from service.core import service_health
```

In `summary()`, before `return StatusSummaryRead(...)`, add:

```python
        services = service_health.collect_service_health(self.settings, self.sources.db)
```

Then include `services=services` in `StatusSummaryRead(...)`:

```python
            services=services,
```

- [ ] **Step 5: Run backend health tests**

Run:

```bash
cd backend
uv run pytest tests/test_service_health.py tests/test_status.py::test_status_summary_includes_platform_service_health -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/service/core/service_health.py backend/service/core/status.py backend/tests/test_service_health.py
git commit -m "feat(status): collect platform service health"
```

## Task 4: Add Celery Beat Heartbeat

**Files:**

- Modify: `backend/service/worker.py`
- Create: `backend/tests/test_worker_heartbeat.py`

- [ ] **Step 1: Write heartbeat test**

Create `backend/tests/test_worker_heartbeat.py`:

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

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/test_worker_heartbeat.py -v
```

Expected: FAIL because `record_beat_heartbeat` does not exist.

- [ ] **Step 3: Implement beat heartbeat task**

In `backend/service/worker.py`, add these imports:

```python
import json
from datetime import UTC, datetime
```

After `celery_app.conf.update(...)`, add:

```python
celery_app.conf.beat_schedule = {
    "lumen-beat-heartbeat": {
        "task": "service.worker.record_beat_heartbeat",
        "schedule": 30.0,
    }
}
```

Add this helper and task before `mark_stale_running_jobs_failed()`:

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

- [ ] **Step 4: Run heartbeat test**

Run:

```bash
cd backend
uv run pytest tests/test_worker_heartbeat.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/service/worker.py backend/tests/test_worker_heartbeat.py
git commit -m "feat(worker): record celery beat heartbeat"
```

## Task 5: Expand Docker Compose Runtime

**Files:**

- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update root environment example**

Add these lines to `.env.example`:

```dotenv
LUMEN_ELASTICSEARCH_URL=http://127.0.0.1:9200
LUMEN_NEO4J_HTTP_URL=http://127.0.0.1:7474
LUMEN_NEO4J_BOLT_URL=bolt://127.0.0.1:7687
LUMEN_NEO4J_USER=neo4j
LUMEN_NEO4J_PASSWORD=lumen-password
LUMEN_SERVICE_HEALTH_TIMEOUT_SECONDS=2
LUMEN_BEAT_HEARTBEAT_MAX_AGE_SECONDS=90
```

Add the same lines to `backend/.env.example`.

- [ ] **Step 2: Add Elasticsearch, Neo4j, and beat to Compose**

Replace `docker-compose.yml` with a version that preserves existing services and adds the new services:

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

- [ ] **Step 3: Validate Compose config**

Run:

```bash
docker compose config >/tmp/lumen-compose-phase0.yml
rg -n "elasticsearch|neo4j|beat|LUMEN_ELASTICSEARCH_URL|LUMEN_NEO4J_HTTP_URL" /tmp/lumen-compose-phase0.yml
```

Expected: output includes the new services and environment variables.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example backend/.env.example
git commit -m "chore(compose): add ES Neo4j and beat services"
```

## Task 6: Render Service Health In Frontend Status

**Files:**

- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/components/StatusPanel.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Update frontend test fixture**

In `frontend/src/test/workbench.test.tsx`, find the mocked `/api/status` JSON response and add this `services` array:

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

In the status page test near the existing `系统状态` assertion, add:

```ts
expect(await screen.findByText('平台服务')).toBeInTheDocument()
expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
expect(screen.getByText('Elasticsearch')).toBeInTheDocument()
expect(screen.getByText('Celery Beat')).toBeInTheDocument()
```

- [ ] **Step 2: Run frontend test to verify it fails**

Run:

```bash
cd frontend
npm run test -- --runInBand src/test/workbench.test.tsx
```

Expected: FAIL because `平台服务` is not rendered or TypeScript type does not include `services`.

- [ ] **Step 3: Add frontend service health types**

In `frontend/src/api/types.ts`, add before `StatusSummaryRead`:

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

Then add this field to `StatusSummaryRead`:

```ts
  services: ServiceHealthRead[]
```

- [ ] **Step 4: Render service health cards**

In `frontend/src/components/StatusPanel.tsx`, add these helper functions above `StatusPanel`:

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

Inside the rendered JSX, after the existing `status-grid` block and before `<IngestionProgressPanel mode="full" />`, insert:

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

- [ ] **Step 5: Add CSS**

In `frontend/src/styles.css`, add near the existing `.status-section` rules:

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

- [ ] **Step 6: Run frontend test**

Run:

```bash
cd frontend
npm run test -- src/test/workbench.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/components/StatusPanel.tsx frontend/src/styles.css frontend/src/test/workbench.test.tsx
git commit -m "feat(status): show platform service health"
```

## Task 7: Update README For Phase 0 Runtime

**Files:**

- Modify: `README.md`

- [ ] **Step 1: Update service list**

In `README.md`, update the Docker Compose service list to include:

```markdown
- 前端：http://127.0.0.1:5173/
- 后端：http://127.0.0.1:8000/
- Postgres：127.0.0.1:5432
- Redis：127.0.0.1:6379
- Elasticsearch：http://127.0.0.1:9200/
- Neo4j Browser：http://127.0.0.1:7474/，默认账号 `neo4j`，密码 `lumen-password`
```

- [ ] **Step 2: Add Phase 0 health smoke**

Add this section after the existing health check snippet:

```markdown
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
```

- [ ] **Step 3: Verify README mentions all services**

Run:

```bash
rg -n "Elasticsearch|Neo4j|平台服务|beat" README.md
```

Expected: output includes the new Phase 0 health section.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document Phase 0 runtime stack"
```

## Task 8: Full Verification

**Files:**

- No new files.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend
uv run pytest tests/test_service_health.py tests/test_worker_heartbeat.py tests/test_status.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend full tests**

Run:

```bash
cd backend
uv run pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd frontend
npm run test
```

Expected: PASS.

- [ ] **Step 4: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS and Vite build output in `frontend/dist`.

- [ ] **Step 5: Validate Compose config**

Run:

```bash
docker compose config >/tmp/lumen-compose-phase0.yml
rg -n "elasticsearch|neo4j|beat|healthcheck" /tmp/lumen-compose-phase0.yml
```

Expected: output includes Elasticsearch, Neo4j, beat, and healthcheck entries.

- [ ] **Step 6: Run full Compose smoke when Docker is available**

Run:

```bash
docker compose up --build
```

Expected:

- PostgreSQL becomes healthy.
- Redis becomes healthy.
- Elasticsearch becomes healthy.
- Neo4j becomes healthy.
- Backend becomes healthy.
- Worker starts.
- Beat starts and creates the heartbeat file through the scheduled task.
- Frontend starts at `http://127.0.0.1:5173/`.

In another terminal:

```bash
curl -s http://127.0.0.1:8000/api/status
```

Expected: response contains `services` with `postgres`, `redis`, `elasticsearch`, `neo4j`, `worker`, and `beat`.

- [ ] **Step 7: Final status check**

Run:

```bash
git status --short
```

Expected: clean working tree except for user-owned unrelated files such as `.claude/` if they were already present.

## Self-Review Checklist

- Spec coverage: implements Phase 0 parity audit, runtime stack, service health, status UI, and docs.
- 文本完整性：计划正文没有未定项、临时标记或让执行者自行补全的步骤。
- Type consistency: backend `ServiceHealthRead` fields match frontend `ServiceHealthRead`.
- Scope control: no auth, ES retrieval, Neo4j graph writes, Agent, research, persona, music, emotion, or notification feature work in Phase 0.
- Verification: backend tests, frontend tests, frontend build, compose config, and optional full Compose smoke are included.
