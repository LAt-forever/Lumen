# Lumen Comet Parity Phase 1 Auth Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add account login and user-scoped data boundaries so existing Lumen data and workflows belong to an authenticated bootstrap user.

**Architecture:** PostgreSQL/SQLite remain the source of truth. The backend adds a `User` model, password hashing, JWT access tokens, a bootstrap user helper, and a `CurrentUser` dependency. Core repositories accept `user_id` and filter owned rows; worker jobs carry `user_id` through the job row. The frontend stores the access token locally, sends it on API requests, and gates the workbench behind a Chinese login screen.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic settings, PyJWT-compatible JWT signing via `python-jose` or an installed equivalent, Passlib/bcrypt if available otherwise stdlib PBKDF2, React, React Query, Vitest.

---

## File Structure

- Create `backend/service/auth.py`: password hashing, token creation/validation, bootstrap user lookup/creation, current user dependency.
- Create `backend/service/api/auth.py`: `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, optional `/api/auth/register` when enabled.
- Modify `backend/service/config.py`: auth settings for secret, token TTL, bootstrap email/password, registration switch.
- Modify `backend/service/models.py`: add `User` and add `user_id` ownership columns to sources, conversations, memory candidates, memories, memory relations, tags, tag assignments, tag suggestions, favorites, ingestion jobs, provider profiles, agent profiles, and tool logs.
- Modify repositories under `backend/service/repositories/`: accept `user_id`, filter reads/writes, and reject cross-user target access.
- Modify `backend/service/worker.py`: read job owner from `ingestion_jobs.user_id` and instantiate scoped repositories.
- Modify API modules under `backend/service/api/`: require current user on business endpoints and pass `user.id` into repositories.
- Modify `backend/alembic/versions/20260618_0001_initial_schema.py`: snapshot now includes auth/user columns through models.
- Create `backend/alembic/versions/20260629_0002_auth_user_scope.py`: migration for existing installations, creating bootstrap user and backfilling existing rows.
- Create `backend/tests/test_auth.py`: login/current-user/register behavior.
- Create `backend/tests/test_user_isolation.py`: cross-user isolation for sources, memories, conversations/chat, jobs, tags, favorites.
- Modify `backend/tests/conftest.py`: test auth helpers and bootstrap defaults.
- Modify `frontend/src/api/client.ts`: token storage, auth API calls, Authorization header, unauthorized callback.
- Modify `frontend/src/api/types.ts`: auth types.
- Create `frontend/src/auth/AuthContext.tsx`: auth state, login/logout/current user bootstrap.
- Create `frontend/src/components/LoginPage.tsx`: Chinese login UI.
- Modify `frontend/src/App.tsx`: wrap app in auth provider and protected workbench.
- Modify or add frontend tests around auth gating and API authorization.
- Modify `README.md`, `.env.example`, and `backend/.env.example`: document auth settings and smoke flow.
- Modify `docs/comet-parity-matrix.md` and `docs/comet-parity-remaining-work.md`: mark Phase 1 completed items as they land.

## Task 1: Backend Auth Foundation

**Files:**
- Create: `backend/service/auth.py`
- Create: `backend/service/api/auth.py`
- Modify: `backend/service/config.py`
- Modify: `backend/service/models.py`
- Modify: `backend/service/schemas.py`
- Modify: `backend/service/api/router.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing auth API tests**

```python
def test_login_returns_access_token_and_current_user(client):
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin-password"})
    assert response.status_code == 200
    token = response.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


def test_login_rejects_bad_password(client):
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_register_is_disabled_by_default(client):
    response = client.post("/api/auth/register", json={"email": "new@example.com", "password": "new-password"})
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: FAIL because `/api/auth/login` is not registered.

- [ ] **Step 3: Implement auth model, schemas, and routes**

Add `User`, auth settings, password hashing, JWT helpers, bootstrap user creation, login/me/logout/register endpoints. Use `LUMEN_BOOTSTRAP_USER_EMAIL=admin@example.com` and `LUMEN_BOOTSTRAP_USER_PASSWORD=admin-password` in tests.

- [ ] **Step 4: Run auth tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_auth.py -v`
Expected: PASS.

## Task 2: User Scope Migration And Repository Boundaries

**Files:**
- Modify: `backend/service/models.py`
- Create: `backend/alembic/versions/20260629_0002_auth_user_scope.py`
- Modify: `backend/service/repositories/sources.py`
- Modify: `backend/service/repositories/memories.py`
- Modify: `backend/service/repositories/conversations.py`
- Modify: `backend/service/repositories/organization.py`
- Modify: `backend/service/repositories/ingestion_jobs.py`
- Test: `backend/tests/test_user_isolation.py`

- [ ] **Step 1: Write failing source isolation test**

```python
def test_sources_are_scoped_to_current_user(client, auth_headers):
    alice = auth_headers("alice@example.com")
    bob = auth_headers("bob@example.com")
    created = client.post("/api/sources", json={"title": "Alice note", "source_type": "note", "content": "private"}, headers=alice)

    assert created.status_code == 200
    assert client.get("/api/sources", headers=alice).json()[0]["title"] == "Alice note"
    assert client.get("/api/sources", headers=bob).json() == []
    assert client.get(f"/api/sources/{created.json()['id']}", headers=bob).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_user_isolation.py::test_sources_are_scoped_to_current_user -v`
Expected: FAIL because source endpoints do not require auth or filter by user.

- [ ] **Step 3: Add ownership columns and scoped repository constructors**

Every owned repository constructor receives `user_id: int`. Create methods write `user_id`; get/list/update/delete methods filter by user. Cross-user reads return `None` or raise `ValueError`, and API handlers map that to 404.

- [ ] **Step 4: Run source isolation test**

Run: `cd backend && uv run pytest tests/test_user_isolation.py::test_sources_are_scoped_to_current_user -v`
Expected: PASS.

## Task 3: Chat, Memory, Organization, And Job Isolation

**Files:**
- Modify: `backend/service/api/chat.py`
- Modify: `backend/service/api/memories.py`
- Modify: `backend/service/api/organization.py`
- Modify: `backend/service/api/ingestion_jobs.py`
- Modify: `backend/service/api/search.py`
- Modify: `backend/service/api/global_search.py`
- Modify: `backend/service/api/review.py`
- Modify: `backend/service/api/status.py`
- Modify: `backend/service/core/chat.py`
- Modify: `backend/service/core/memory.py`
- Modify: `backend/service/core/knowledge.py`
- Modify: `backend/service/core/tagging.py`
- Modify: `backend/service/core/global_search.py`
- Test: `backend/tests/test_user_isolation.py`

- [ ] **Step 1: Write failing isolation tests for each named domain**

Cover memories, chat conversations/messages, ingestion jobs, tags, and favorites. Use two logged-in users and assert Bob cannot list, fetch, mutate, tag, favorite, cancel, or retry Alice-owned records.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_user_isolation.py -v`
Expected: FAIL on unscoped repository reads.

- [ ] **Step 3: Pass `CurrentUser` through business APIs**

Every business API gets `current_user: User = Depends(get_current_user)` and constructs repositories with `current_user.id`.

- [ ] **Step 4: Run user isolation tests**

Run: `cd backend && uv run pytest tests/test_user_isolation.py -v`
Expected: PASS.

## Task 4: Worker User Scope

**Files:**
- Modify: `backend/service/worker.py`
- Modify: `backend/service/api/ingestion_jobs.py`
- Modify: `backend/service/repositories/ingestion_jobs.py`
- Test: `backend/tests/test_ingestion_worker.py`

- [ ] **Step 1: Write failing worker scope test**

Create a job owned by Alice and a source with the same id lookup risk owned by Bob if possible; run `run_ingestion_job(job.id)` and assert only Alice's source/job records are changed.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_ingestion_worker.py::test_worker_uses_job_user_scope -v`
Expected: FAIL because worker repositories are global.

- [ ] **Step 3: Make worker instantiate scoped repositories from `job.user_id`**

Load the job first, read `job.user_id`, then instantiate `SourceRepository(db, user_id=job.user_id)`, `ChunkRepository(db, user_id=job.user_id)`, and `IngestionJobRepository(db, user_id=job.user_id)`.

- [ ] **Step 4: Run worker tests**

Run: `cd backend && uv run pytest tests/test_ingestion_worker.py -v`
Expected: PASS.

## Task 5: Frontend Auth Gate

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/components/LoginPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/test/workbench.test.tsx`

- [ ] **Step 1: Write failing frontend auth test**

Render `<App />` with no token and assert the login form is shown. Mock `/api/auth/login` and assert successful login shows the workbench nav. Mock a request and assert `Authorization: Bearer <token>` is sent.

- [ ] **Step 2: Run frontend test to verify it fails**

Run: `cd frontend && npm test -- --run src/test/workbench.test.tsx`
Expected: FAIL because no auth gate exists.

- [ ] **Step 3: Implement token storage and protected shell**

Store token in `localStorage` under `lumen.accessToken`, call `/api/auth/me` on load, show `LoginPage` until authenticated, and clear token on logout or 401.

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run src/test/workbench.test.tsx`
Expected: PASS.

## Task 6: Documentation And Smoke

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `backend/.env.example`
- Modify: `docs/comet-parity-matrix.md`
- Modify: `docs/comet-parity-remaining-work.md`

- [ ] **Step 1: Document auth environment variables**

Include `LUMEN_BOOTSTRAP_USER_EMAIL`, `LUMEN_BOOTSTRAP_USER_PASSWORD`, `LUMEN_AUTH_SECRET_KEY`, `LUMEN_ACCESS_TOKEN_EXPIRE_MINUTES`, and `LUMEN_REGISTRATION_ENABLED`.

- [ ] **Step 2: Document smoke flow**

Add: start stack, log in with bootstrap user, create a note, ask a question, confirm a memory, create tag/favorite, log out, verify a second user cannot see records.

- [ ] **Step 3: Update parity tracking**

Mark completed Phase 1 items and leave remaining deeper modules untouched.

- [ ] **Step 4: Run final verification**

Run:

```bash
cd backend && uv run pytest
cd frontend && npm test -- --run
cd frontend && npm run build
docker compose up --build
```

Expected: backend tests pass, frontend tests pass, frontend builds, and compose stack exposes healthy backend/frontend/platform services. If Docker daemon is unavailable, record the skipped Docker verification in the final response.

## Self-Review

- Spec coverage: This plan covers the Phase 1 checklist: user model, login, password hashing, JWT access tokens, session decision, current user, logout, registration switch, bootstrap admin, frontend login/auth/protected routes, owned data backfill, repository scope, worker scope, cross-user tests, and docs.
- Placeholder scan: No `TBD` or open-ended implementation placeholders remain; each task has concrete file targets and commands.
- Type consistency: The plan consistently uses `user_id`, `User`, `get_current_user`, and `lumen.accessToken`.
