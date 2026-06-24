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
