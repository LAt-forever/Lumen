from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from service.db import Base
from service.repositories.ingestion_jobs import IngestionJobRepository
from service.repositories.sources import SourceRepository
from service.schemas import SourceCreate


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_ingestion_job_lifecycle_records_progress_and_timestamps():
    db = make_session()
    sources = SourceRepository(db)
    jobs = IngestionJobRepository(db)
    source = sources.create(SourceCreate(title="Queue note", source_type="note", content="Queue me."))

    job = jobs.create(
        job_type="note",
        batch_id="batch-alpha",
        source_id=source.id,
        payload_json='{"source_id": 1}',
        progress_total=3,
        message="等待处理",
    )

    assert job.id is not None
    assert job.status == "queued"
    assert job.progress_current == 0
    assert job.progress_total == 3
    assert job.message == "等待处理"
    assert job.error_message is None
    assert job.source_id == source.id
    assert job.source.title == "Queue note"

    queued = jobs.mark_queued(job.id, "celery-1")
    assert queued.celery_task_id == "celery-1"
    assert queued.status == "queued"

    running = jobs.mark_running(job.id)
    assert running.status == "running"
    assert isinstance(running.started_at, datetime)

    progressed = jobs.update_progress(job.id, 2, 3, "正在建立索引")
    assert progressed.progress_current == 2
    assert progressed.progress_total == 3
    assert progressed.message == "正在建立索引"

    succeeded = jobs.mark_succeeded(job.id, "索引完成")
    assert succeeded.status == "succeeded"
    assert succeeded.progress_current == 3
    assert succeeded.progress_total == 3
    assert succeeded.message == "索引完成"
    assert succeeded.error_message is None
    assert isinstance(succeeded.finished_at, datetime)


def test_ingestion_job_lists_batches_counts_and_stale_running_jobs():
    db = make_session()
    jobs = IngestionJobRepository(db)
    queued = jobs.create(job_type="link", batch_id="batch-beta", source_id=None, payload_json="{}", message="等待")
    running = jobs.create(job_type="crawl", batch_id="batch-beta", source_id=None, payload_json="{}", message="抓取")
    failed = jobs.create(job_type="upload", batch_id="batch-gamma", source_id=None, payload_json="{}", message="失败")

    jobs.mark_running(running.id)
    jobs.mark_failed(failed.id, "解析失败")

    recent = jobs.list_recent(limit=10)
    assert [job.id for job in recent] == [failed.id, running.id, queued.id]
    assert [job.id for job in jobs.list_recent(status="running")] == [running.id]
    assert [job.id for job in jobs.list_for_batch("batch-beta")] == [queued.id, running.id]
    assert [job.id for job in jobs.stale_running_jobs()] == [running.id]
    assert jobs.status_counts() == {
        "queued": 1,
        "running": 1,
        "succeeded": 0,
        "failed": 1,
        "canceled": 0,
    }


def test_cancel_only_changes_queued_jobs():
    db = make_session()
    jobs = IngestionJobRepository(db)
    queued = jobs.create(job_type="note", batch_id="batch-cancel", source_id=None, payload_json="{}")
    running = jobs.create(job_type="link", batch_id="batch-cancel", source_id=None, payload_json="{}")
    jobs.mark_running(running.id)

    canceled = jobs.cancel_queued(queued.id)
    assert canceled is not None
    assert canceled.status == "canceled"
    assert canceled.finished_at is not None

    assert jobs.cancel_queued(running.id) is None
