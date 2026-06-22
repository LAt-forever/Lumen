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
