# Lumen

Lumen is a personal AI knowledge base and long-term memory assistant.

## Phase 1

The first version focuses on the core loop:

- capture notes and sources
- index knowledge
- ask questions with citations
- extract pending memory candidates
- confirm or ignore memory candidates
- review recent sources and memories

## Run Backend

```bash
cd backend
uv sync
uv run uvicorn service.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Test

```bash
cd backend
uv run pytest -v

cd ../frontend
npm run test
npm run build
```
