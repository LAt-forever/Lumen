# Lumen Comet Parity Phase 3 Image Document Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first Phase 3 slice: image library, source asset metadata/status surfaces, and visible retry for parse/index failures.

**Architecture:** Keep `Source` as the user-facing knowledge item and add `SourceAsset` as durable metadata for uploaded or captured artifacts. `SourceDetailRead` becomes the source detail aggregate, combining source fields, asset rows, chunk status summary, indexing runs, tags/favorite state, and retry eligibility. The frontend adds an Image Library view and upgrades source detail to display parse, embedding, ES index, graph sync, asset metadata, and retry actions.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Celery worker, pytest, React, TanStack Query, Vitest.

---

## File Structure

- Create `backend/alembic/versions/20260630_0004_source_assets_phase3.py`: source asset table and backfill.
- Create `backend/service/repositories/source_assets.py`: scoped CRUD and status helpers.
- Modify `backend/service/models.py`: `SourceAsset` model and `Source.assets` relationship.
- Modify `backend/service/schemas.py`: asset, indexing run, source detail, and image library response schemas.
- Modify `backend/service/core/storage.py`: file metadata helper for stored uploads.
- Modify `backend/service/core/ingestion.py`: create/update source assets during upload parse/index.
- Modify `backend/service/core/knowledge.py`: update asset embedding/index status alongside `IndexingRun`.
- Modify `backend/service/api/sources.py`: return enriched details, list image sources, expose retry-ready state.
- Modify `backend/service/worker.py`: avoid duplicate indexing for retry jobs.
- Create or modify backend tests in `backend/tests/test_source_assets.py`, `backend/tests/test_sources.py`, and `backend/tests/test_ingestion_worker.py`.
- Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, and `frontend/src/api/hooks.ts`: add Phase 3 response types and image listing hook.
- Modify `frontend/src/App.tsx` and `frontend/src/components/AppShell.tsx`: add Image Library navigation.
- Create `frontend/src/components/ImageLibraryPanel.tsx`: image library surface.
- Modify `frontend/src/components/SourceList.tsx`: enriched source detail.
- Modify `frontend/src/test/workbench.test.tsx`: image library and detail assertions.

## Task 1: Backend Asset Metadata and Source Detail Contract

- [x] Write failing tests in `backend/tests/test_source_assets.py`.

```python
def test_upload_image_records_asset_metadata_and_detail_status(client):
    png_bytes = b"\x89PNG\r\n\x1a\n" + (b"0" * 128)
    response = client.post(
        "/api/ingestion-jobs/uploads",
        files=[("files", ("diagram.png", png_bytes, "image/png"))],
    )
    assert response.status_code == 200
    source_id = response.json()["sources"][0]["id"]

    detail = client.get(f"/api/sources/{source_id}")

    assert detail.status_code == 200
    body = detail.json()
    assert body["source_type"] == "image"
    assert body["assets"][0]["filename"] == "diagram.png"
    assert body["assets"][0]["mime_type"] == "image/png"
    assert body["assets"][0]["byte_size"] == len(png_bytes)
    assert body["assets"][0]["parse_status"] in {"pending", "parsed", "failed"}
    assert body["embedding_status"] in {"pending", "embedded", "skipped", "failed"}
    assert body["index_status"] in {"pending", "indexed", "skipped", "failed"}
    assert body["graph_status"] == "pending"
    assert isinstance(body["indexing_runs"], list)
```

- [x] Run `cd backend && uv run pytest tests/test_source_assets.py::test_upload_image_records_asset_metadata_and_detail_status -q` and confirm it fails because asset fields do not exist.
- [x] Add `SourceAsset` model, schema, repository, migration, and upload asset creation.
- [x] Enrich `GET /api/sources/{source_id}` with `assets`, chunk-derived embedding/index summary, graph status, indexing runs, `can_retry`, tags, and favorite state.
- [x] Run the same test and confirm it passes.

## Task 2: Image Library API

- [x] Write failing API tests in `backend/tests/test_source_assets.py`.

```python
def test_image_library_lists_only_images_in_active_knowledge_base(client):
    first = client.post("/api/knowledge-bases", json={"name": "Images A"}).json()
    second = client.post("/api/knowledge-bases", json={"name": "Images B"}).json()
    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={first['id']}",
        files=[("files", ("alpha.png", b"\x89PNG\r\n\x1a\nalpha", "image/png"))],
    )
    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={second['id']}",
        files=[("files", ("beta.png", b"\x89PNG\r\n\x1a\nbeta", "image/png"))],
    )
    client.post(
        f"/api/ingestion-jobs/uploads?knowledge_base_id={first['id']}",
        files=[("files", ("notes.txt", b"not an image", "text/plain"))],
    )

    response = client.get(f"/api/sources/images?knowledge_base_id={first['id']}")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["alpha.png"]
    assert response.json()[0]["asset"]["filename"] == "alpha.png"
```

- [x] Run `cd backend && uv run pytest tests/test_source_assets.py::test_image_library_lists_only_images_in_active_knowledge_base -q` and confirm it fails because the route does not exist.
- [x] Add `GET /api/sources/images` using the active knowledge base scope and `SourceAssetRepository`.
- [x] Run the API test and confirm it passes.

## Task 3: Retry and Worker Status Consistency

- [x] Write failing tests for failed parse/index visibility and retry behavior.
- [x] Update ingestion/knowledge services so source asset `parse_status`, `embedding_status`, `index_status`, and error fields mirror parse/index outcomes.
- [x] Fix worker retry jobs so `retry_source()` is not followed by a second `index_existing_source()` call.
- [x] Run `cd backend && uv run pytest tests/test_source_assets.py tests/test_ingestion_worker.py -q`.

## Task 4: Frontend Image Library and Detail Surfaces

- [x] Write failing Vitest assertions in `frontend/src/test/workbench.test.tsx` for:
  - sidebar Image Library navigation,
  - `GET /api/sources/images?knowledge_base_id=<id>`,
  - image cards with OCR/vision/search status,
  - source detail metadata/status/retry controls.
- [x] Add `SourceAssetRead`, `SourceIndexingRunRead`, `SourceImageRead`, and enriched `SourceDetailRead` types.
- [x] Add `api.listImages()` and `useImageSources()`.
- [x] Add `ImageLibraryPanel` and the image route.
- [x] Update `SourceList` details to show asset metadata, parse, embedding, ES index, graph sync, latest indexing run, tags/favorite, and retry.
- [x] Run `cd frontend && npm test -- --run src/test/workbench.test.tsx`.

## Task 5: Verification and Docs

- [x] Run backend targeted tests:

```bash
cd backend && uv run pytest tests/test_source_assets.py tests/test_sources.py tests/test_ingestion_worker.py tests/test_ingestion_jobs_api.py -q
```

- [x] Run frontend targeted tests:

```bash
cd frontend && npm test -- --run src/test/workbench.test.tsx
```

- [x] Run full validation if targeted tests pass:

```bash
cd backend && uv run pytest
cd frontend && npm test -- --run
cd frontend && npm run build
cd backend && LUMEN_DATABASE_URL=sqlite:////private/tmp/lumen-phase3-assets-alembic.db uv run alembic -c alembic.ini upgrade head
```

- [x] Update `docs/comet-parity-remaining-work.md` and `docs/comet-parity-matrix.md` to mark completed Phase 3 items.

## Completion Addendum

- Remote embedding indexing now writes source chunks to Elasticsearch projection automatically. If ES projection fails, source/chunk/asset/indexing run status is failed; local hash indexing remains skipped.
- Image parser output is covered by search and chat citation tests, so OCR/vision text is searchable and citable through the normal RetrievalService path.
- Web link/bookmark/crawl sources can enqueue a refresh job through `/api/ingestion-jobs/sources/{source_id}/refresh`; the frontend exposes this from Source Detail.
- Image Library and Source Detail preserve tag and favorite state for images and documents.
