from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

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
