# Lumen Ingestion Jobs Design

## Overview

This phase turns Lumen ingestion from request-bound parsing into a persistent worker-backed pipeline. The current FastAPI handlers parse files, crawl pages, import bookmarks, and index chunks inside the HTTP request. That works for a local prototype, but it makes OCR, Playwright crawls, and batch imports block the UI and provides no durable progress surface.

The new design introduces a persistent `IngestionJob` model, Celery workers, Redis for queue transport, and a Docker Compose runtime that runs Postgres, Redis, backend, worker, and frontend together. The frontend submits ingestion work through a new job API, then shows progress in the Status view and a compact right-column panel.

## Goals

- Queue every user-facing ingestion entry point through the new job API.
- Persist job history, progress, errors, Celery task ids, and batch grouping in the application database.
- Keep `Source.status` as the source lifecycle state while adding `IngestionJob.status` for task lifecycle state.
- Support per-item jobs grouped by `batch_id` for uploads and bookmark imports.
- Support canceling queued jobs and retrying failed or canceled jobs.
- Add a full Docker Compose local stack with Postgres, Redis, backend, worker, and frontend.
- Keep non-Docker local development possible with SQLite and a user-provided Redis instance.
- Preserve legacy `/api/sources/*` endpoints for compatibility during this phase.

## Non-Goals

- No running-task hard kill or Celery revoke workflow in the first version.
- No task priority, scheduling, pause/resume, or distributed worker routing strategy.
- No keychain/API-key protection changes.
- No graph editing or reranker configuration.
- No removal of the legacy synchronous source endpoints.
- No full migration framework; the project still uses the current `Base.metadata.create_all()` prototype approach.

## Current State

The slow paths live in `backend/service/api/sources.py`:

- `POST /api/sources/upload` reads uploaded files, parses content, and indexes each source inside the request.
- `POST /api/sources/crawl` runs Playwright crawl parsing and indexing inside the request.
- `POST /api/sources/link` fetches, parses, and indexes a webpage inside the request.
- `POST /api/sources/bookmarks` parses bookmarks and performs concurrent link capture with a shared SQLAlchemy session.
- `POST /api/sources/{source_id}/index` and `/retry` perform parsing or indexing inline.

The frontend `CapturePanel` treats ingestion mutation pending state as a global busy state. That is appropriate for short HTTP requests, but not for long-running OCR, crawl, and batch import work. The `StatusPanel` already owns runtime health, source counts, failed sources, and repair actions, so it is the natural home for the full progress panel.

## Architecture

### Runtime Components

The Docker Compose runtime contains:

- `postgres`: primary application database for the Compose stack.
- `redis`: Celery broker and result backend.
- `backend`: FastAPI API service.
- `worker`: Celery worker using the same backend code and shared upload volume.
- `frontend`: React/Vite frontend pointed at the backend service.

Manual non-Docker development remains supported:

- FastAPI can still run with SQLite through `LUMEN_DATABASE_URL=sqlite:///./lumen.db`.
- A Celery worker can be started manually with `uv run celery -A service.worker worker --loglevel=info --concurrency=1`.
- Redis must be provided by the developer when running the worker locally.

### Data Ownership

The database is the source of truth for user-visible job state. Redis is transport infrastructure, not the source of truth. Celery task ids are stored on `IngestionJob`, but the frontend reads progress from Lumen APIs backed by the database.

Workers open their own SQLAlchemy sessions. They never reuse request-scoped sessions from FastAPI dependencies.

### Concurrency

The first Docker worker defaults to one worker process. This avoids SQLite local lock surprises in non-Docker mode and prevents OCR or Playwright from saturating the machine. Compose uses Postgres by default for better API/worker concurrent writes.

## Data Model

Add `IngestionJob` in `backend/service/models.py`.

Fields:

- `id`: integer primary key.
- `batch_id`: string UUID, indexed. Jobs from one user submission share a batch id.
- `source_id`: nullable foreign key to `sources.id`.
- `job_type`: string enum-like value.
- `status`: string enum-like value.
- `progress_current`: integer, default `0`.
- `progress_total`: integer, default `1`.
- `message`: nullable text for user-visible progress.
- `error_message`: nullable text for failure details.
- `payload_json`: text payload needed by the worker.
- `celery_task_id`: nullable string.
- `created_at`, `updated_at`, `started_at`, `finished_at`: timestamps.

Job types:

- `note`
- `upload`
- `link`
- `crawl`
- `bookmark`
- `index`
- `retry`

Job statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`

`Source.status` remains:

- `pending`
- `parsing`
- `indexed`
- `failed`

Relationship:

- A job may reference one source.
- A source may have many jobs over time, especially after retry or reindex operations.
- A batch is represented by shared `batch_id`, not a separate table in the first version.

## Backend Services

### Repository

Create `backend/service/repositories/ingestion_jobs.py` with methods that mirror current repository style:

- `create(job_type, batch_id, source_id, payload_json, progress_total=1, message=None)`
- `get(job_id)`
- `list_recent(status=None, batch_id=None, limit=50)`
- `list_for_batch(batch_id)`
- `mark_queued(job_id, celery_task_id)`
- `mark_running(job_id, celery_task_id=None)`
- `update_progress(job_id, current, total, message)`
- `mark_succeeded(job_id, message=None)`
- `mark_failed(job_id, error_message)`
- `cancel_queued(job_id)`
- `stale_running_jobs()`

Repository methods commit their own changes, consistent with existing repositories.

### Worker Orchestration

Create `backend/service/worker.py`, exposing `celery_app` and job task entry points.

The worker flow:

1. Load job by id using a fresh session.
2. If status is `canceled`, skip the job and return.
3. Mark job `running`, set `started_at`, and set source status to `parsing` where a source exists.
4. Dispatch by `job_type`.
5. Parse or index using existing parser and `KnowledgeService` boundaries.
6. Update progress and message at meaningful phase boundaries.
7. On success, mark the referenced source `indexed` and mark the job `succeeded`.
8. On failure, mark the referenced source `failed` and mark the job `failed`.

Startup recovery:

- When the worker starts, it finds stale `running` jobs and marks them failed with a clear stale-worker message. The user can retry them.
- `queued` jobs remain queued and can be picked up by Celery tasks that still exist in Redis. If a queued database row exists without a Celery task id because enqueue failed, it is marked failed during enqueue handling instead of silently waiting forever.

### Parser Extraction

The source API currently contains parsing/indexing orchestration inline. This phase extracts reusable functions into `backend/service/core/ingestion.py`, so both API compatibility paths and Celery worker paths call the same source-processing logic.

The service should cover:

- note/text indexing
- uploaded file parsing
- link parsing
- crawl parsing
- bookmark link parsing
- existing source reindex
- retry handling

The worker must not share SQLAlchemy sessions across concurrent bookmark items. Each job owns one source and one database session.

## API Design

Legacy `/api/sources/*` endpoints remain available.

Add `backend/service/api/ingestion_jobs.py` mounted under `/api/ingestion-jobs`.

### Submission Endpoints

- `POST /api/ingestion-jobs/notes`
  - Body: title/content source payload.
  - Creates one source and one job.

- `POST /api/ingestion-jobs/uploads`
  - Multipart multi-file upload.
  - Creates one source and one job per file.
  - All jobs share one `batch_id`.

- `POST /api/ingestion-jobs/links`
  - Body: URL.
  - Creates one link source and one job.

- `POST /api/ingestion-jobs/crawls`
  - Body: URL, max depth, max pages, same-domain setting.
  - Creates one web crawl source and one job.

- `POST /api/ingestion-jobs/bookmarks`
  - Body: Netscape bookmark HTML.
  - Parses bookmark entries synchronously enough to create one source and one job per bookmark.
  - All jobs share one `batch_id`.

- `POST /api/ingestion-jobs/sources/{source_id}/index`
  - Creates one index job for an existing source.

### Query and Control Endpoints

- `GET /api/ingestion-jobs`
  - Query params: `status`, `batch_id`, `limit`.
  - Returns recent jobs for progress panels.

- `GET /api/ingestion-jobs/{job_id}`
  - Returns one job.

- `GET /api/ingestion-jobs/batches/{batch_id}`
  - Returns the batch aggregate and child jobs.

- `POST /api/ingestion-jobs/{job_id}/cancel`
  - Cancels only `queued` jobs.
  - Returns 409 for running, succeeded, or failed jobs.

- `POST /api/ingestion-jobs/{job_id}/retry`
  - Creates a new job for a failed or canceled job.
  - Keeps old job history.

### Responses

Single and batch submission endpoints return a batch-shaped response:

```json
{
  "batch_id": "uuid",
  "total": 2,
  "queued": 2,
  "jobs": [],
  "sources": []
}
```

`IngestionJobRead` includes:

- `id`
- `batch_id`
- `source_id`
- `source_title`
- `job_type`
- `status`
- `progress_current`
- `progress_total`
- `message`
- `error_message`
- `created_at`
- `updated_at`
- `started_at`
- `finished_at`

Broker unavailable behavior:

- New submission endpoints return 503 with a user-facing queue runtime message.
- They do not silently fall back to synchronous parsing.
- If a source was created before enqueue failure, the API records a failed job, marks that source failed, and removes any temporary upload file that has not been moved into final source storage.

## Frontend Design

### Capture Panel

`CapturePanel` switches ingestion actions to the new job endpoints:

- Add note -> `/api/ingestion-jobs/notes`
- Upload files -> `/api/ingestion-jobs/uploads`
- Add link -> `/api/ingestion-jobs/links`
- Deep crawl -> `/api/ingestion-jobs/crawls`
- Import bookmarks -> `/api/ingestion-jobs/bookmarks`

Submission success shows a queued message and the batch summary. The form resets after a successful enqueue, not after worker completion.

`isBusy` means "the submit request is in flight." It no longer remains busy while Celery jobs are running.

### Progress Panel

Create `frontend/src/components/IngestionProgressPanel.tsx`.

Full mode in Status view:

- Shows recent batches.
- Shows recent jobs.
- Shows counts for queued, running, succeeded, failed, canceled.
- Shows per-job title, type, status, progress, message, and error.
- Supports cancel for queued jobs.
- Supports retry for failed or canceled jobs.
- Disables cancel for running jobs with a short explanation.

Compact mode in the right context column:

- Shows the most recent active jobs, capped at a small number.
- Provides a link-like button or text cue to open the Status view.
- Avoids crowding `CapturePanel`.

### Polling

React Query polling rules:

- Poll every 1.5-2 seconds when any job is queued or running.
- Slow down or disable polling when there are no active jobs.
- Invalidate sources, source detail, status, search, and review queries when jobs complete or fail.

### Labels

Add job status labels:

- queued: 排队中
- running: 处理中
- succeeded: 已完成
- failed: 失败
- canceled: 已取消

Add job type labels:

- note: 笔记
- upload: 文件
- link: 链接
- crawl: 深度抓取
- bookmark: 书签
- index: 重建索引
- retry: 重试

## Docker Compose

Add root `docker-compose.yml`.

Services:

- `postgres`
  - Uses a named volume such as `postgres-data`.
  - Provides the default Compose database.

- `redis`
  - Used by Celery broker and result backend.

- `backend`
  - Builds from `backend/Dockerfile`.
  - Runs FastAPI.
  - Depends on Postgres and Redis.
  - Shares a data volume with worker.

- `worker`
  - Builds from the same backend image.
  - Runs Celery worker.
  - Depends on Postgres and Redis.
  - Shares the data volume with backend.
  - Defaults to one worker process.

- `frontend`
  - Builds from `frontend/Dockerfile`.
  - Serves the React app for local development.
  - Points `VITE_API_BASE` at the backend port available to the browser.

Environment:

- `LUMEN_DATABASE_URL=postgresql+psycopg://lumen:lumen@postgres:5432/lumen`
- `LUMEN_CELERY_BROKER_URL=redis://redis:6379/0`
- `LUMEN_CELERY_RESULT_BACKEND=redis://redis:6379/1`
- `VITE_API_BASE=http://127.0.0.1:8000`

Backend image:

- Installs Python dependencies through uv.
- Installs system packages needed by current parsers: Tesseract, English and Simplified Chinese OCR language data, and Playwright Chromium dependencies.
- Installs Playwright Chromium during image build.

Frontend image:

- Installs npm dependencies.
- Runs the Vite dev server for this prototype.

README updates:

- Add `docker compose up --build`.
- Add health check for backend.
- Add a smoke flow: submit a note, observe queued/running/succeeded in Status, ask a question after indexing completes.
- Keep manual backend/frontend commands for non-Docker development.

## Error Handling

- Broker unavailable: new job submission returns 503 and the UI says the queue service is not running.
- Parser failure: job `failed`, source `failed`, error stored on both records when the job references a source.
- Worker restart during running job: stale running job becomes failed with retry available.
- Upload save failure: no job is enqueued and temp files are cleaned where possible.
- Enqueue failure after source creation: job is failed, source is failed, and any remaining temporary upload file is removed before the response returns.
- Cancel queued: job `canceled`; source remains visible but not indexed. User can retry or delete the source.
- Cancel running: rejected with 409; UI explains running jobs cannot be canceled in this version.

## Testing Strategy

Backend tests:

- `IngestionJobRepository` lifecycle.
- Submission endpoints create sources and jobs without indexing synchronously.
- Upload endpoint returns one job per file with a shared batch id.
- Bookmark endpoint returns one job per bookmark with a shared batch id.
- Worker success marks source indexed, creates chunks, and marks job succeeded.
- Worker failure marks source failed and job failed.
- Queued cancel works and running cancel returns 409.
- Failed/canceled retry creates a new job.
- Status summary includes an ingestion job summary with queued, running, succeeded, failed, and canceled counts.
- Broker unavailable returns 503 for new ingestion endpoints.

Frontend tests:

- CapturePanel submits to new job endpoints and shows queued feedback.
- StatusPanel renders queued, running, succeeded, failed, and canceled jobs.
- Failed job retry and queued job cancel call the expected endpoints.
- Active jobs enable polling.
- Source list still uses source status for library state.

Docker smoke:

- `docker compose up --build`.
- `GET /healthz` succeeds.
- Submit one note through the frontend or API.
- Worker indexes it.
- Status view shows completion.
- Search or chat can use the indexed content.

## Acceptance Criteria

This phase is complete when:

- Every frontend ingestion action uses `/api/ingestion-jobs/*`.
- Every submitted ingestion item has a persisted job row.
- Bulk uploads and bookmark imports group item jobs by `batch_id`.
- The worker processes queued jobs through Celery and updates durable progress.
- Status view displays recent jobs, active progress, failures, retry, and queued cancellation.
- Docker Compose starts Postgres, Redis, backend, worker, and frontend.
- Manual non-Docker development remains documented.
- Legacy source endpoints still pass compatibility tests.
- Backend tests, frontend tests, frontend build, and Docker smoke pass.
