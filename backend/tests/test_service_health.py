from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from service.config import Settings
from service.core.service_health import (
    check_beat_heartbeat,
    check_postgres,
    check_redis,
    check_worker,
    collect_service_health,
    service_result,
)
from service.schemas import ServiceHealthRead


def _health(name: str, status: str = "ok", detail: str | None = None) -> ServiceHealthRead:
    labels = {
        "postgres": "PostgreSQL",
        "redis": "Redis",
        "elasticsearch": "Elasticsearch",
        "neo4j": "Neo4j",
        "worker": "Celery Worker",
        "beat": "Celery Beat",
    }
    return ServiceHealthRead(
        name=name,
        label=labels[name],
        status=status,
        detail=detail or f"{name} ok",
        latency_ms=1.0,
        checked_at=datetime(2026, 6, 22, tzinfo=UTC),
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


def test_check_redis_sets_connect_timeout_and_closes_client(monkeypatch):
    calls = {}

    class FakeRedis:
        def ping(self):
            calls["pinged"] = True

        def close(self):
            calls["closed"] = True

    def fake_from_url(url, socket_timeout=None, socket_connect_timeout=None):
        calls["url"] = url
        calls["socket_timeout"] = socket_timeout
        calls["socket_connect_timeout"] = socket_connect_timeout
        return FakeRedis()

    monkeypatch.setattr("service.core.service_health.Redis.from_url", fake_from_url)
    settings = Settings(celery_broker_url="redis://health-check", service_health_timeout_seconds=0.25)

    result = check_redis(settings)

    assert result.name == "redis"
    assert result.status == "ok"
    assert calls == {
        "url": "redis://health-check",
        "socket_timeout": 0.25,
        "socket_connect_timeout": 0.25,
        "pinged": True,
        "closed": True,
    }


def test_check_worker_reports_broker_unavailable_without_celery_inspect(monkeypatch):
    calls = {}

    class FakeRedis:
        def ping(self):
            raise TimeoutError("redis down")

        def close(self):
            calls["closed"] = True

    def fake_from_url(url, socket_timeout=None, socket_connect_timeout=None):
        calls["url"] = url
        calls["socket_timeout"] = socket_timeout
        calls["socket_connect_timeout"] = socket_connect_timeout
        return FakeRedis()

    class FakeCelery:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Celery inspect should not run when broker is unavailable")

    monkeypatch.setattr("service.core.service_health.Redis.from_url", fake_from_url)
    monkeypatch.setattr("service.core.service_health.Celery", FakeCelery)
    settings = Settings(celery_broker_url="redis://health-check", service_health_timeout_seconds=0.25)

    result = check_worker(settings)

    assert result.name == "worker"
    assert result.label == "Celery Worker"
    assert result.status == "unavailable"
    assert result.detail.startswith("broker unavailable: redis down")
    assert calls == {
        "url": "redis://health-check",
        "socket_timeout": 0.25,
        "socket_connect_timeout": 0.25,
        "closed": True,
    }


def test_check_worker_preserves_no_worker_replied_detail(monkeypatch):
    calls = {}

    class FakeRedis:
        def ping(self):
            calls["broker_pinged"] = True

        def close(self):
            calls["broker_closed"] = True

    def fake_from_url(url, socket_timeout=None, socket_connect_timeout=None):
        calls["socket_timeout"] = socket_timeout
        calls["socket_connect_timeout"] = socket_connect_timeout
        return FakeRedis()

    class FakeInspect:
        def ping(self):
            return {}

    class FakeControl:
        def inspect(self, timeout=None):
            calls["inspect_timeout"] = timeout
            return FakeInspect()

    class FakeCelery:
        def __init__(self, name, broker=None, backend=None):
            calls["celery_name"] = name
            calls["celery_broker"] = broker
            calls["celery_backend"] = backend
            self.conf = self
            self.control = FakeControl()

        def update(self, **kwargs):
            calls["celery_conf"] = kwargs

        def close(self):
            calls["celery_closed"] = True

    monkeypatch.setattr("service.core.service_health.Redis.from_url", fake_from_url)
    monkeypatch.setattr("service.core.service_health.Celery", FakeCelery)
    settings = Settings(
        celery_broker_url="redis://health-check",
        celery_result_backend="redis://health-results",
        service_health_timeout_seconds=0.25,
    )

    result = check_worker(settings)

    assert result.name == "worker"
    assert result.status == "unavailable"
    assert result.detail == "no worker replied"
    assert calls == {
        "socket_timeout": 0.25,
        "socket_connect_timeout": 0.25,
        "broker_pinged": True,
        "broker_closed": True,
        "celery_name": "lumen-health",
        "celery_broker": "redis://health-check",
        "celery_backend": "redis://health-results",
        "celery_conf": {
            "broker_connection_timeout": 0.25,
            "broker_connection_retry": False,
            "broker_connection_retry_on_startup": False,
            "broker_connection_max_retries": 0,
            "broker_transport_options": {
                "socket_timeout": 0.25,
                "socket_connect_timeout": 0.25,
                "retry_on_timeout": False,
                "max_retries": 0,
            },
            "result_backend_transport_options": {
                "socket_timeout": 0.25,
                "socket_connect_timeout": 0.25,
                "retry_on_timeout": False,
                "max_retries": 0,
            },
        },
        "inspect_timeout": 0.25,
        "celery_closed": True,
    }


def test_collect_service_health_skips_worker_when_redis_unavailable(monkeypatch):
    calls = []

    def fake_http(name, label, url, timeout_seconds):
        calls.append(("http", name, url, timeout_seconds))
        return _health(name)

    def fail_worker(settings, check_broker=True):
        raise AssertionError("worker check should be skipped when redis is unavailable")

    monkeypatch.setattr("service.core.service_health.check_postgres", lambda db: _health("postgres"))
    monkeypatch.setattr(
        "service.core.service_health.check_redis",
        lambda settings: _health("redis", "unavailable", "redis connection refused"),
    )
    monkeypatch.setattr("service.core.service_health.check_http_json", fake_http)
    monkeypatch.setattr("service.core.service_health.check_worker", fail_worker)
    monkeypatch.setattr("service.core.service_health.check_beat_heartbeat", lambda settings: _health("beat"))

    results = collect_service_health(Settings(), db_session=object())

    assert [result.name for result in results] == ["postgres", "redis", "elasticsearch", "neo4j", "worker", "beat"]
    worker = results[4]
    assert worker.status == "unavailable"
    assert worker.detail == "broker unavailable: redis connection refused"
    assert {call[1] for call in calls} == {"elasticsearch", "neo4j"}


def test_collect_service_health_reuses_ok_redis_and_skips_worker_broker_check(monkeypatch):
    calls = []

    def fake_http(name, label, url, timeout_seconds):
        calls.append(("http", name, url, timeout_seconds))
        return _health(name)

    def fake_worker(settings, check_broker=True):
        calls.append(("worker", check_broker))
        assert check_broker is False
        return _health("worker", "unavailable", "no worker replied")

    settings = Settings(elasticsearch_url="http://search.example/")
    monkeypatch.setattr("service.core.service_health.check_postgres", lambda db: _health("postgres"))
    monkeypatch.setattr("service.core.service_health.check_redis", lambda settings: _health("redis"))
    monkeypatch.setattr("service.core.service_health.check_http_json", fake_http)
    monkeypatch.setattr("service.core.service_health.check_worker", fake_worker)
    monkeypatch.setattr("service.core.service_health.check_beat_heartbeat", lambda settings: _health("beat"))

    results = collect_service_health(settings, db_session=object())

    assert [result.name for result in results] == ["postgres", "redis", "elasticsearch", "neo4j", "worker", "beat"]
    assert ("http", "elasticsearch", "http://search.example/_cluster/health", settings.service_health_timeout_seconds) in calls
    assert ("http", "neo4j", settings.neo4j_http_url, settings.service_health_timeout_seconds) in calls
    assert ("worker", False) in calls


def test_check_beat_heartbeat_reports_missing_file(tmp_path):
    settings = Settings(beat_heartbeat_path=tmp_path / "missing.json")

    result = check_beat_heartbeat(settings)

    assert result.name == "beat"
    assert result.status == "unavailable"
    assert result.detail == "heartbeat file not found"


def test_check_beat_heartbeat_reports_stat_error(monkeypatch):
    class BrokenStatPath:
        def exists(self):
            return True

        def stat(self):
            raise OSError("permission denied")

    monkeypatch.setattr("service.core.service_health._heartbeat_path", lambda settings: BrokenStatPath())

    result = check_beat_heartbeat(Settings())

    assert result.name == "beat"
    assert result.status == "unavailable"
    assert result.detail == "heartbeat stat failed: permission denied"


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
