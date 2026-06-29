from pathlib import Path

from service.config import get_settings
from service import db as dbmod
from service.models import IngestionJob
from service.repositories.chunks import ChunkRepository
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.indexing_runs import IndexingRunRepository
from service.repositories.knowledge_bases import KnowledgeBaseRepository
from service.repositories.sources import SourceRepository
from service.schemas import KnowledgeBaseCreate, SourceCreate


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
        runs = IndexingRunRepository(db)
        refreshed_source = sources.get(source_id)
        refreshed_job = jobs.get(job_id)
        chunk = chunks.list_all()[0]
        run = runs.list_for_source(source_id)[0]
        assert refreshed_source.status == "indexed"
        assert refreshed_job.status == "succeeded"
        assert refreshed_job.progress_current == refreshed_job.progress_total
        assert refreshed_job.finished_at is not None
        assert chunks.count_for_source(source_id) >= 1
        assert chunk.user_id == refreshed_source.user_id
        assert chunk.knowledge_base_id == refreshed_source.knowledge_base_id
        assert chunk.content_hash
        assert chunk.embedding_status in ("embedded", "skipped")
        assert chunk.index_status in ("indexed", "skipped")
        assert run.status == "succeeded"
        assert run.job_id == job_id
        assert run.chunks_total >= 1
        assert run.chunks_embedded >= 1


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


def test_worker_failure_marks_existing_indexing_run_failed(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    with dbmod.SessionLocal() as db:
        sources = SourceRepository(db)
        jobs = IngestionJobRepository(db)
        source = sources.create(SourceCreate(title="Broken index", source_type="note", content="Broken indexing content."))
        job = jobs.create(
            job_type="note",
            batch_id="batch-worker-index-fail",
            source_id=source.id,
            payload_json=f'{{"source_id": {source.id}}}',
            progress_total=3,
        )
        source_id = source.id
        job_id = job.id

    def fail_replace(*args, **kwargs):
        raise RuntimeError("chunk write failed")

    monkeypatch.setattr(ChunkRepository, "replace_for_source", fail_replace)

    from service.worker import run_ingestion_job

    run_ingestion_job(job_id)

    with dbmod.SessionLocal() as db:
        job_after = IngestionJobRepository(db).get(job_id)
        run = IndexingRunRepository(db).list_for_source(source_id)[0]
        assert job_after.status == "failed"
        assert run.status == "failed"
        assert "chunk write failed" in run.error_message


def test_worker_uses_job_knowledge_base_scope(tmp_path, monkeypatch):
    setup_database(tmp_path, monkeypatch)
    with dbmod.SessionLocal() as db:
        knowledge_bases = KnowledgeBaseRepository(db)
        source_kb = knowledge_bases.create(KnowledgeBaseCreate(name="Source KB"))
        job_kb = knowledge_bases.create(KnowledgeBaseCreate(name="Job KB"))
        sources = SourceRepository(db, knowledge_base_id=source_kb.id)
        source = sources.create(SourceCreate(title="Mismatched scope", source_type="note", content="Mismatched content."))
        job = IngestionJob(
            knowledge_base_id=job_kb.id,
            job_type="note",
            batch_id="batch-worker-scope",
            source_id=source.id,
            payload_json=f'{{"source_id": {source.id}, "knowledge_base_id": {job_kb.id}}}',
            progress_total=3,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        source_id = source.id
        job_id = job.id

    from service.worker import run_ingestion_job

    run_ingestion_job(job_id)

    with dbmod.SessionLocal() as db:
        source_after = SourceRepository(db).get(source_id)
        job_after = IngestionJobRepository(db).get(job_id)
        assert source_after.status == "pending"
        assert job_after.status == "failed"
        assert "not found" in job_after.error_message


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
