# Chat Bot RAG Full

Ứng dụng chatbot RAG tra cứu văn bản pháp luật Việt Nam, nâng từ bản demo local sang bản production-friendly theo đúng hướng roadmap: FastAPI + Streamlit + PostgreSQL + Qdrant + `llama.cpp` OpenAI-compatible.

## Thành phần chính

- `FastAPI`: API cho chat, ingest tài liệu, legal search
- `Streamlit`: giao diện chat và quản lý tài liệu
- `PostgreSQL`: lưu document metadata, chunks, chat history khi cấu hình `DATABASE_URL`
- `Qdrant`: vector store thật khi cấu hình `QDRANT_URL`
- `llama.cpp`: LLM và embedding server OpenAI-compatible qua `LLM_BASE_URL` và `EMBEDDING_BASE_URL`
- Fallback local: nếu chưa bật Postgres/Qdrant/llama.cpp thì app vẫn chạy bằng local JSON store + local hash embedding + extractive answerer

## Các cải tiến đã thêm

- Rerank lai giữa vector score và lexical overlap
- Chat history được đưa vào pipeline trả lời
- Citation validation để phát hiện dẫn chiếu không nằm trong ngữ cảnh truy xuất
- Ingest file `txt`, `md`, `html`, `htm`, `pdf`
- Adapter tách biệt cho local và production store

## Cấu trúc quan trọng

- [app/main.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/main.py): entrypoint FastAPI
- [app/services/rag.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/services/rag.py): retrieval, rerank, chat history, citation warnings
- [app/services/document.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/services/document.py): ingest text/uploaded files
- [app/services/parser.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/services/parser.py): parse `html/pdf/txt`
- [app/db/postgres.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/db/postgres.py): local metadata store + PostgreSQL metadata store
- [app/db/qdrant.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/db/qdrant.py): local vector store + Qdrant vector store
- [docker-compose.yml](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/docker-compose.yml): stack production local

## Chạy local nhanh

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload
```

Mở docs tại `http://127.0.0.1:8000/docs`.

Chạy Streamlit:

```bash
uv run streamlit run streamlit_app/Home.py
```

## Chạy full stack bằng Docker Compose

Nếu muốn chỉ chạy app + Postgres + Qdrant + Streamlit:

```bash
docker compose up --build
```

Nếu muốn bật luôn `llama.cpp` LLM và embedding server:

```bash
docker compose --profile llama up --build
```

Điều kiện:

- đặt file GGUF vào thư mục `models/`
- `qwen2.5-7b-instruct-q4_k_m.gguf`
- `Qwen3-Embedding-0.6B-Q8_0.gguf`

## Cấu hình môi trường

Biến quan trọng trong [`.env.example`](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/.env.example):

- `DATABASE_URL`: bật PostgreSQL metadata/chat history
- `QDRANT_URL`: bật vector store Qdrant
- `QDRANT_COLLECTION`: nên giữ `legal_chunks_qwen3` cho bộ embedding hiện tại
- `LLM_BASE_URL`, `LLM_MODEL`: trỏ tới `llama.cpp` chat server
- `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`: trỏ tới `llama.cpp` embedding server

Nếu bỏ trống các biến trên, app dùng local fallback.

Lưu ý:
- `.env.example` dùng cổng PostgreSQL host là `5433` để khớp với `docker-compose.yml`
- embedding hiện tại dùng chiều vector `1024`; nếu đổi model hoặc dimension thì cần reindex và nên dùng collection Qdrant mới

## API chính

- `GET /health`
- `GET /api/documents`
- `POST /api/documents/ingest`
- `POST /api/documents/upload`
- `POST /api/documents/preload`
- `POST /api/chat/query`
- `GET /api/legal/search`

## Test

```bash
uv run pytest
```

Smoke test runtime sau khi bật Docker:

```bash
bash scripts/smoke_test.sh
```

Workflow nhanh bằng `Makefile`:

```bash
make up
make test
make smoke
make ps
make logs-api
```
