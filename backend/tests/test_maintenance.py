import json
import sqlite3
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.db import Base
from service.maintenance import (
    backup_sqlite,
    cleanup_ingestion_jobs,
    export_sqlite_ndjson,
    restore_sqlite,
)
from service.repositories.ingestion_jobs import IngestionJobRepository


def _make_sqlite(path: Path):
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute("INSERT INTO sample (name) VALUES ('alpha')")
    connection.commit()
    connection.close()


def test_backup_and_restore_sqlite_round_trip(tmp_path):
    db_path = tmp_path / "lumen.db"
    _make_sqlite(db_path)

    backup = backup_sqlite(db_path, tmp_path / "backup.zip")
    restored = restore_sqlite(backup.backup_path, tmp_path / "restored.db")

    assert restored.exists()
    with zipfile.ZipFile(backup.backup_path) as archive:
        assert {"database.sqlite", "metadata.json"}.issubset(set(archive.namelist()))
    connection = sqlite3.connect(restored)
    try:
        assert connection.execute("SELECT name FROM sample").fetchone()[0] == "alpha"
    finally:
        connection.close()


def test_export_sqlite_ndjson_writes_manifest_and_tables(tmp_path):
    db_path = tmp_path / "lumen.db"
    _make_sqlite(db_path)

    counts = export_sqlite_ndjson(db_path, tmp_path / "export")

    assert counts == {"sample": 1}
    assert json.loads((tmp_path / "export" / "manifest.json").read_text())["tables"] == {"sample": 1}
    assert json.loads((tmp_path / "export" / "sample.ndjson").read_text().strip())["name"] == "alpha"


def test_cleanup_ingestion_jobs_deletes_old_terminal_rows():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    jobs = IngestionJobRepository(db)
    old = jobs.create("note", "old", None, "{}", message="old")
    recent = jobs.create("note", "recent", None, "{}", message="recent")
    running = jobs.create("note", "running", None, "{}", message="running")
    jobs.mark_failed(old.id, "old failure")
    jobs.mark_failed(recent.id, "recent failure")
    jobs.mark_running(running.id)
    old_id = old.id
    recent_id = recent.id
    running_id = running.id

    db.get(type(old), old_id).finished_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=45)
    db.commit()

    result = cleanup_ingestion_jobs(db, older_than_days=30)

    assert result.deleted_count == 1
    assert jobs.get(old_id) is None
    assert jobs.get(recent_id) is not None
    assert jobs.get(running_id) is not None
