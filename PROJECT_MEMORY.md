# Project Memory

## Current State

This project started from `LEARNING-ROADMAP.md` and has already been implemented as a working legal RAG chatbot.

The current system supports:
- FastAPI backend
- Streamlit frontend
- document ingest for `txt`, `md`, `html`, `pdf`
- local fallback embeddings and extractive answering
- production adapters for PostgreSQL and Qdrant
- local `llama.cpp` OpenAI-compatible servers for chat and embeddings
- conversation memory by `conversation_id`

## Production Stack

Docker Compose includes:
- `api`
- `streamlit`
- `postgres`
- `qdrant`
- `llama-llm`
- `llama-embed`

Host ports:
- API `8000`
- Streamlit `8501`
- Postgres `5433`
- Qdrant `6333`
- llama chat `8080`
- llama embedding `8081`

## Local Models

Models stored in `models/`:
- `qwen2.5-7b-instruct-q4_k_m.gguf`
- `Qwen3-Embedding-0.6B-Q8_0.gguf`

The embedding dimension is `1024`.

## Important Features Already Added

### RAG

- chunking by legal article structure
- citation extraction and validation
- vector retrieval
- reranking with lexical overlap
- follow-up chat using stored conversation history

### Conversation Memory

Conversation memory is already implemented in the app:
- each chat uses `conversation_id`
- history is stored in local metadata or PostgreSQL
- API supports create/list/get/delete conversation
- Streamlit supports new conversation and deleting current conversation

Main files:
- `app/api/chat.py`
- `app/services/rag.py`
- `app/db/postgres.py`
- `streamlit_app/pages/1_Chat.py`

## Validation Baseline

Last verified commands:
- `python3 -m compileall app streamlit_app tests`
- `uv run pytest -q`
- `docker compose --profile llama up -d --build`
- `bash scripts/smoke_test.sh`
- `GET /health`
- `POST /api/documents/preload`
- `GET /api/legal/search?q=Dieu17&top_k=3`
- `POST /api/chat/query`

The latest test result was `12 passed`.

Live Docker flow was also verified for:
- preload documents
- legal search
- chat with citations
- conversation memory across multiple turns

## Recent Updates

- Added session-based conversation memory with `conversation_id`.
- Added conversation APIs for create, list, get history, and delete.
- Updated Streamlit chat UI to keep the active conversation and manage chat sessions.
- Verified latest baseline with `10 passed`.
- Aligned repo defaults around the current Qwen3 embedding setup:
  `EMBEDDING_DIMENSION=1024`, `QDRANT_COLLECTION=legal_chunks_qwen3`,
  and host PostgreSQL port `5433` in `.env.example`.
- Added `.dockerignore` and expanded `.gitignore` for local caches, reports,
  and GGUF model files to keep the repo and Docker build context cleaner.
- Added a minimal GitHub Actions workflow at `.github/workflows/pytest.yml`
  to run `uv sync --dev` and `uv run pytest -q` on pushes and pull requests.
- Re-verified the full Docker llama profile locally: API, Streamlit, llama chat,
  llama embedding, PostgreSQL, and Qdrant all started successfully and the main
  ingest/search/chat endpoints responded as expected.
- Added `scripts/smoke_test.sh` to validate the core runtime flow with one command:
  health, preload, legal search, and chat query.
- Improved legal search recall for explicit article references such as `Dieu17`
  by normalizing unaccented queries and merging exact article matches from
  metadata when vector retrieval misses them.
- Added `PRODUCTION_ROADMAP.md` as the durable production-hardening plan for
  moving the current legal RAG app from POC to an operational deployment.
- Added a root `Makefile` for the standard operator workflow:
  `make up`, `make test`, `make smoke`, `make ps`, and log helpers.

## Change Guidance

When improving this project later, prefer this order:
1. Read `AGENTS.md`
2. Read this file
3. Read only the directly relevant modules
4. Run targeted tests first, then full tests

## Known Constraints

- Without `llama.cpp`, the app still works but quality falls back to local deterministic embeddings and extractive answering.
- When changing vector dimensions or embedding providers, reindex documents and use a separate Qdrant collection.
