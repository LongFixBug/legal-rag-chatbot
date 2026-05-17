# Chatbot RAG Luật Nghĩa Vụ Quân Sự

Ứng dụng chatbot RAG chuyên trả lời câu hỏi về nghĩa vụ quân sự Việt Nam: độ tuổi gọi nhập ngũ, tiêu chuẩn nhập ngũ, tạm hoãn/miễn gọi nhập ngũ, khám sức khỏe, cận thị và xử phạt. Kiến trúc vẫn production-friendly: FastAPI + Streamlit + PostgreSQL + Qdrant + `llama.cpp` OpenAI-compatible.

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
- Corpus demo mặc định chỉ preload các file `nghia-vu-quan-su-curated-*.txt`
- Direct-answer layer riêng cho câu hỏi nghĩa vụ quân sự thường gặp
- Endpoint reindex sạch để xoá dữ liệu preload cũ rồi nạp lại corpus curated

## Cấu trúc quan trọng

- [app/main.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/main.py): entrypoint FastAPI
- [app/services/rag.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/services/rag.py): retrieval, rerank, chat history, citation warnings
- [app/services/military.py](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/app/services/military.py): phân loại và trả lời trực tiếp các câu hỏi nghĩa vụ quân sự phổ biến
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
- `PRELOAD_INCLUDE_PATTERN`: mặc định `nghia-vu-quan-su-curated-*.txt` để demo chỉ nạp corpus nghĩa vụ quân sự đã làm sạch
- `QDRANT_URL`: bật vector store Qdrant
- `QDRANT_COLLECTION`: nên giữ `legal_chunks_qwen3` cho bộ embedding hiện tại
- `LLM_BASE_URL`, `LLM_MODEL`: trỏ tới `llama.cpp` chat server
- `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`: timeout và retry policy cho chat backend
- `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`: trỏ tới `llama.cpp` embedding server
- `EMBEDDING_TIMEOUT_SECONDS`, `EMBEDDING_MAX_RETRIES`: timeout và retry policy cho embedding backend

Nếu bỏ trống các biến trên, app dùng local fallback.

Lưu ý:
- `.env.example` dùng cổng PostgreSQL host là `5433` để khớp với `docker-compose.yml`
- embedding hiện tại dùng chiều vector `1024`; nếu đổi model hoặc dimension thì cần reindex và nên dùng collection Qdrant mới
- với `llama.cpp`, `LLM_MODEL` và `EMBEDDING_MODEL` nên đặt đúng theo `id` từ `/v1/models`, hiện tại là tên file `.gguf`
- text/PDF trích xuất thô được giữ trong `data/raw/` để đối chiếu, không dùng làm corpus preload

## API chính

- `GET /health`
- `GET /health/ready`
- `GET /api/documents`
- `POST /api/documents/ingest`
- `POST /api/documents/upload`
- `POST /api/documents/preload`
- `POST /api/documents/reindex`
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
make eval
make eval-generate
make smoke
make ps
make ready
make logs-api
```

Ghi chú vận hành:
- `/health` là liveness check đơn giản
- `/health/ready` là readiness check theo dependency
- `/health/ready` có thể trả `status: "degraded"` nhưng vẫn `ready: true` nếu remote LLM hoặc embedding backend lỗi nhưng local fallback vẫn phục vụ được

## Quality eval

Bộ eval nằm ở [evals/legal_quality_cases.json](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/evals/legal_quality_cases.json) và được chạy bằng:

```bash
make eval
```

Eval đang tách ba nhóm:
- `retrieval`: câu hỏi phải kéo đúng văn bản/chunk
- `answer`: câu trả lời phải có cụm bắt buộc và tránh cụm sai đã biết
- `calculation`: hiện để trống vì demo đã khóa phạm vi vào nghĩa vụ quân sự, không còn chạy domain thuế

Khi thêm nhiều văn bản luật mới, có thể sinh bản nháp eval trước:

```bash
make eval-generate
```

Lệnh này ghi `evals/generated_candidates.json` từ các file `data/*.txt`. File này là bản nháp cục bộ và không commit; hãy duyệt các case tốt rồi mới đưa những case đại diện vào [evals/legal_quality_cases.json](/Users/nguyenhailong/Documents/Chat-bot-RAG-full/evals/legal_quality_cases.json). Nếu muốn chạy riêng một file generated đã duyệt, dùng `INCLUDE_GENERATED_EVALS=1 GENERATED_EVAL_CASES_PATH=evals/generated_cases.json uv run pytest tests/test_quality_eval.py -q`.

Để sinh nháp cho một văn bản cụ thể:

```bash
uv run python scripts/generate_eval_candidates.py --file nghia-vu-quan-su-curated-luat-hop-nhat-80-2025.txt
```

## Cập nhật nguồn nghĩa vụ quân sự

Tải lại PDF nguồn chính thức vào `data/raw/nghia-vu-quan-su/`:

```bash
uv run python scripts/import_military_docs.py
```

Nếu muốn thử trích xuất text thô để đối chiếu:

```bash
uv run python scripts/import_military_docs.py --extract-text
```
