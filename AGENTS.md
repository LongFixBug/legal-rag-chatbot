# Project Instructions

## Goal

This repository is a legal RAG chatbot with:
- FastAPI backend
- Streamlit frontend
- Qdrant vector store
- PostgreSQL metadata/chat history
- local `llama.cpp` servers for chat and embeddings

## First Read

Before making broad changes, read `PROJECT_MEMORY.md`.
Use `HANDOFF_TEMPLATE.md` when ending a non-trivial work session.

## Runtime

Preferred stack:
- `docker compose --profile llama up -d --build`

Main endpoints:
- API: `http://127.0.0.1:8000`
- Streamlit: `http://127.0.0.1:8501`
- LLM server: `http://127.0.0.1:8080`
- Embedding server: `http://127.0.0.1:8081`

## Key Paths

- `app/main.py`: FastAPI entrypoint
- `app/services/rag.py`: retrieval + rerank + answer generation + conversation memory
- `app/services/document.py`: ingest/upload pipeline
- `app/db/postgres.py`: local store + PostgreSQL store
- `app/db/qdrant.py`: Qdrant adapter
- `app/api/chat.py`: chat and conversation APIs
- `streamlit_app/pages/1_Chat.py`: chat UI
- `tests/`: regression coverage

## Working Rules

- Preserve the current Docker flow and env-based adapter switching.
- Do not remove fallback local mode unless explicitly requested.
- Keep conversation memory isolated by `conversation_id`.
- When touching retrieval or storage, run tests and verify the chat flow still works.
- After any non-trivial code or architecture change, update `PROJECT_MEMORY.md`.
- Keep `PROJECT_MEMORY.md` concise: record current state, changed architecture, validation baseline, and open constraints.
- When ending a session with unfinished follow-up work, leave a short handoff note based on `HANDOFF_TEMPLATE.md`.

## Validation

Default validation:
- `uv run pytest -q`

If Docker services are running, also verify:
- `GET /health`
- `POST /api/documents/preload`
- `POST /api/chat/query`
