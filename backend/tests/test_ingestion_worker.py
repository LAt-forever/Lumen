from pathlib import Path

from service.config import get_settings
from service import db as dbmod
from service.repositories.chunks import ChunkRepository
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def setup_database(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LUMEN_LLM_MODE", "extractive")
    get_settings.cache_clear()
    dbmod.configure_database(f"sqlite:///{tmp_path / 'worker.db'}")
    dbmod.init_db()


def test_worker_indexes_note_job_and_marks_source_indexed(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    with dbmod.SessionLocal() as db:
        sources = SourceRepository(db)
        jobs = IngestionJobRepository(db)
        source = sources.create(SourceCreate(title="Worker note", source_type="note", content="WorkerMarker content."))
        job = jobs.create(
            job_type="note",
            batch_id="batch-worker",
            source_id=source.id,
            payload_json=f'{{"source_id": {source.id}}}',
            progress_total=3,
        )
        source_id = source.id
        job_id = job.id

    from service.worker import run_ingestion_job

    run_ingestion_job(job_id)

    with dbmod.SessionLocal() as db:
        sources = SourceRepository(db)
        jobs = IngestionJobRepository(db)
        chunks = ChunkRepository(db)
        refreshed_source = sources.get(source_id)
        refreshed_job = jobs.get(job_id)
        assert refreshed_source.status == "indexed"
        assert refreshed_job.status == "succeeded"
        assert refreshed_job.progress_current == refreshed_job.progress_total
        assert refreshed_job.finished_at is not None
        assert chunks.count_for_source(source_id) >= 1


def test_worker_failure_marks_job_and_source_failed(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    with dbmod.SessionLocal() as db:
        sources = SourceRepository(db)
        jobs = IngestionJobRepository(db)
        source = sources.create(SourceCreate(title="Empty", source_type="note", content=""))
        job = jobs.create(
            job_type="retry",
            batch_id="batch-worker-fail",
            source_id=source.id,
            payload_json=f'{{"source_id": {source.id}}}',
            progress_total=3,
        )
        source_id = source.id
        job_id = job.id

    from service.worker import run_ingestion_job

    run_ingestion_job(job_id)

    with dbmod.SessionLocal() as db:
        source_after = SourceRepository(db).get(source_id)
        job_after = IngestionJobRepository(db).get(job_id)
        assert source_after.status == "failed"
        assert job_after.status == "failed"
        assert "No text content found" in job_after.error_message


def test_stale_running_jobs_are_failed_on_worker_recovery(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    with dbmod.SessionLocal() as db:
        jobs = IngestionJobRepository(db)
        job = jobs.create(job_type="note", batch_id="batch-stale", source_id=None, payload_json="{}")
        jobs.mark_running(job.id)

    from service.worker import mark_stale_running_jobs_failed

    mark_stale_running_jobs_failed()

    with dbmod.SessionLocal() as db:
        job_after = IngestionJobRepository(db).get(job.id)
        assert job_after.status == "failed"
        assert "worker stopped before finishing" in job_after.error_message
