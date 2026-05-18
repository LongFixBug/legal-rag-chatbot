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

The latest test result was `32 passed`.

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
- Started Phase 1 hardening:
  added config validation for remote model settings, explicit timeout/retry
  settings for LLM and embedding backends, and a new `/health/ready` endpoint
  backed by dependency readiness checks for metadata, vector store, LLM, and
  embedding services.
- Updated the smoke script and local operator workflow to include readiness
  checks in addition to liveness checks.
- Refined readiness semantics so the app can report `degraded` while still
  remaining `ready` when remote model services fail but local fallback modes
  keep the chatbot operational.
- Aligned the configured `LLM_MODEL` and `EMBEDDING_MODEL` values with the
  actual `/v1/models` ids exposed by `llama.cpp` to avoid false degraded
  readiness due to model-name mismatch.
- Added a worker-personal-income-tax corpus to `data/`:
  `Luật 109/2025/QH15`, `Nghị quyết 110/2025/UBTVQH15`,
  `VBHN 04/2007/QH12 + 26/2012/QH13`, `Nghị định 65/2013/NĐ-CP`,
  and `Thông tư 111/2013/TT-BTC`.
- Added `scripts/import_worker_tax_docs.py` to re-import those worker-tax
  documents from official public sources and cleaned the HTML extraction used
  for `Nghị quyết 110/2025/UBTVQH15` so only article body text is indexed.
- Updated preload hygiene so `data/README.md` is skipped instead of being
  ingested into the legal corpus.
- Expanded title detection to recognize `Nghị định`, `Nghị quyết`, `Thông tư`,
  and `Văn bản hợp nhất`, which keeps tax-document titles stable in the UI and
  retrieval output.
- Added a topical title/phrase fallback in retrieval so short resolutions and
  natural-language tax questions like `giảm trừ gia cảnh 2026` can surface the
  right worker-tax materials even when vector recall is weak.
- Added a deterministic prize-winning tax path for questions such as
  `trúng số 2 tỷ`: retrieval now merges `trúng thưởng` chunks, the answer layer
  calculates the 10% tax on the amount above the applicable threshold, and the
  prompt explicitly prevents applying salary progressive tax brackets to
  trúng thưởng/xổ số questions.
- Added a direct inheritance/gift tax path for questions such as
  `được thừa kế 3 tỷ thì có đóng thuế không`: the answer layer now explains the
  asset-type assumption, computes both the old/new 10% thresholds, and filters
  citation noise so the UI no longer shows unrelated procedure clauses for this
  case.
- Added structured legal quality evals in `evals/legal_quality_cases.json` with
  separate retrieval, answer, and calculation checks. `make eval` runs these
  focused RAG quality tests before broader regression testing.
- Expanded the eval corpus with group labels such as `tax.prize`,
  `tax.inheritance`, `tax.family`, `business.rights`, `investment.policy`, and
  `investment.restrictions`, plus an `EVAL_GROUPS` filter so a subset of domain
  cases can be run independently.
- Added `scripts/generate_eval_candidates.py` and `make eval-generate` to create
  draft eval cases from `data/*.txt`. The generator detects important legal
  articles, creates retrieval/answer candidates, and writes the ignored local
  draft `evals/generated_candidates.json` for manual review before selected cases
  are copied into `evals/legal_quality_cases.json`.
- Added `tax.disability` handling for questions like
  `tôi bị khuyết tật thì đóng thuế như thế nào`: retrieval now boosts disability,
  tax-reduction, exempt compensation, and dependent-relief contexts, while the
  answer layer explains that disability does not automatically exempt all PIT and
  separates taxable income, possible tax reduction, exempt benefits, and dependent
  deductions.
- Added `tax.liability` handling for questions like
  `người trong độ tuổi lao động phải đáp ứng điều kiện nào thì sẽ đóng thuế tncn`:
  the answer layer now explains that working age is not the deciding condition,
  and retrieval prioritizes PIT taxpayer, taxable-income, salary-income, family
  deduction, and non-resident salary-tax articles.
- Latest regression baseline: `env UV_CACHE_DIR=.uv-cache uv run pytest -q`
  passed with `36 passed`, and the live Docker app was reloaded after the
  inheritance-tax citation filtering change.
- Latest full regression baseline after the eval expansion:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `42 passed`.
- Latest full regression baseline after disability-tax handling:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `45 passed`.
- Latest full regression baseline after adding the eval candidate generator:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `46 passed`.
- Latest full regression baseline after tax-liability handling:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `49 passed`.
- Fixed the eval-generator workflow so generated drafts are opt-in instead of
  automatically expanding the default regression suite. `make eval-generate`
  now writes `evals/generated_candidates.json`; generated suites can be run
  explicitly with `INCLUDE_GENERATED_EVALS=1`.
- Improved the local extractive fallback answer format so it starts with a
  direct `Câu trả lời ngắn` summary before listing the main citations, instead
  of only dumping retrieved legal chunks.
- Removed the hardcoded `3 tỷ` wording from inheritance/gift tax answers and
  normalized RAG query expansion with accent folding.
- Latest validation after fallback/eval workflow cleanup:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `49 passed`.
- Optional generated eval validation:
  `env UV_CACHE_DIR=.uv-cache INCLUDE_GENERATED_EVALS=1 GENERATED_EVAL_CASES_PATH=evals/generated_cases.json uv run pytest tests/test_quality_eval.py -q`
  passed with `589 passed`.
- Pivoted the demo scope from broad legal/tax Q&A to a focused Vietnamese
  military-service-law chatbot.
- Added military-service corpus files covering Luật Nghĩa vụ quân sự 2015,
  Thông tư 105/2023/TT-BQP health/eyesight standards, and the administrative
  penalty flow from Nghị định 120/2013/NĐ-CP as amended by Nghị định
  37/2022/NĐ-CP.
- Added `app/services/military.py` as the direct-answer layer for military
  service law intents: age, duration, standards, student deferment,
  deferment/exemption, health/eyesight, exam summons, and penalties.
- Updated Streamlit and README messaging for the military-service-law demo.
- Latest validation after the military-service pivot:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `59 passed`.
- Downloaded official military-service-law source documents from Công báo into
  `data/raw/nghia-vu-quan-su/`, including VBHN 80/VBHN-VPQH, Law
  98/2025/QH15, VBHN 36/VBHN-BQP, VBHN 88/VBHN-BQP, VBHN 75/VBHN-BQP,
  VBHN 76/VBHN-BQP, VBHN 40/VBHN-BQP, and VBHN 04/VBHN-BQP.
- Updated the preload corpus summaries for military service law to reflect the
  latest 2025 consolidated texts, especially Article 42 authority now being
  Chủ tịch UBND cấp tỉnh after Law 98/2025/QH15.
- Kept low-quality text extracted from scanned/source-weak PDFs under
  `data/raw/nghia-vu-quan-su/extracted-*.txt` so the app does not preload those
  noisy chunks into the RAG index.
- Narrowed the default legal quality eval suite to military-service-law cases
  so it matches the current focused demo scope and the remaining data corpus.
- Added confidence/abstain behavior to the chat response so the app refuses
  weakly grounded answers instead of confidently answering from poor retrieval.
- Added optional `ADMIN_TOKEN` protection for mutating document endpoints:
  ingest, upload, preload, reindex, and delete.
- Expanded the focused military-service-law eval suite to cover common demo
  questions across age, duration, student deferment, deferment/exemption,
  health/eyesight, exam summons, penalties, female service, discharge, and
  out-of-scope handling.
- Polished the Streamlit chat demo with military-service sample questions and
  debug-only confidence/abstain metadata.
- Added a GitHub Actions Docker image build job alongside the pytest job.
- Latest validation after confidence/admin/eval/UI/CI hardening:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with
  `107 passed, 1 skipped`; `python3 -m compileall app streamlit_app tests`
  passed; `docker build -t legal-rag-chatbot:ci .` passed.
- Tightened runtime preload to `PRELOAD_INCLUDE_PATTERN=nghia-vu-quan-su-curated-*.txt`
  and renamed the clean corpus files with a `curated` prefix so Docker/demo no
  longer indexes raw OCR or `pdftotext` output by accident.
- Added `/api/documents/reindex` and Streamlit reindex controls so preload data
  can be refreshed cleanly instead of accumulating stale OCR/index chunks.
- Simplified the active RAG runtime to the military-service-law domain only:
  out-of-scope questions now receive a scope message, and legacy tax-specific
  runtime helpers/import scripts were removed.
- Hid debug details such as retrieval scores, chunk count, and conversation id
  behind Streamlit debug toggles, while keeping citations visible as readable
  legal grounds.
- Expanded military-service eval coverage for female service, discharge, only
  child/deferment, and out-of-scope behavior; updated smoke tests and generator
  defaults around the military-service demo scope.
- Latest validation after the military-only hardening pass:
  `env UV_CACHE_DIR=.uv-cache uv run pytest -q` passed with `55 passed, 1 skipped`;
  `python3 -m compileall app streamlit_app scripts tests` also passed.

## Change Guidance

When improving this project later, prefer this order:
1. Read `AGENTS.md`
2. Read this file
3. Read only the directly relevant modules
4. Run targeted tests first, then full tests

## Known Constraints

- Without `llama.cpp`, the app still works but quality falls back to local deterministic embeddings and extractive answering.
- When changing vector dimensions or embedding providers, reindex documents and use a separate Qdrant collection.
