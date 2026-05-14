# Production Roadmap

## Capability

Mục tiêu là nâng legal RAG chatbot hiện tại từ một POC đã chạy được thành một dịch vụ nội bộ hoặc production nhỏ có thể vận hành ổn định, kiểm soát rủi ro tốt, quan sát được, và nâng cấp dần mà không phá vỡ Docker flow hiện tại. Sau khi hoàn thành roadmap này, hệ thống phải giữ được các năng lực hiện có như ingest, legal search, chat với citation, conversation memory theo `conversation_id`, đồng thời bổ sung guardrail vận hành, triển khai, bảo mật, và chất lượng truy xuất đủ để phục vụ người dùng thật.

## Constraints

- Giữ Docker flow hiện tại làm đường chạy chuẩn: `docker compose --profile llama up -d --build`.
- Không bỏ local fallback mode nếu chưa có yêu cầu rõ ràng.
- Conversation memory phải tiếp tục cô lập theo `conversation_id`.
- Khi đổi embedding model hoặc vector dimension phải reindex và dùng collection Qdrant mới.
- Stack hiện tại dùng FastAPI, Streamlit, PostgreSQL, Qdrant, `llama.cpp`; roadmap nên ưu tiên tiến hóa trên nền này trước khi thay platform.
- Đây là chatbot pháp lý nên câu trả lời phải ưu tiên truy xuất có căn cứ, tránh tạo cảm giác “tư vấn pháp lý tuyệt đối”.

## Implementation Contract

### Actors

- Người dùng cuối: hỏi đáp pháp lý, xem citation, tiếp tục hội thoại.
- Operator/dev: khởi động stack, ingest dữ liệu, kiểm tra health, debug lỗi, deploy phiên bản mới.
- Maintainer: nâng model, đổi cấu hình retrieval, chạy migration, theo dõi chất lượng hệ thống.

### Surfaces

- FastAPI: `/health`, `/api/documents/*`, `/api/chat/*`, `/api/legal/search`
- Streamlit UI: chat, documents, legal search
- PostgreSQL: metadata, chat history
- Qdrant: vector storage
- `llama.cpp`: chat và embedding backend
- Local scripts/CI: `uv run pytest -q`, `bash scripts/smoke_test.sh`

### States And Transitions

- `POC-ready`
  Điều kiện: local tests pass, Docker stack lên được, core endpoints trả kết quả.
- `production-hardening`
  Điều kiện: có config tách môi trường, CI ổn định, health/smoke/backup/logging rõ ràng.
- `controlled-release`
  Điều kiện: có migration path, monitoring, rollback, secret management, rate limiting hoặc auth tối thiểu.
- `operational-production`
  Điều kiện: có SLO nội bộ, alerting, runbook, data lifecycle, quality evaluation định kỳ.

### Data And Interface Implications

- `chat/query` phải tiếp tục trả `conversation_id`, `citations`, `validation_warnings`.
- `documents/preload` và ingest flow cần idempotent hơn ở môi trường thật.
- Qdrant collection naming phải gắn với embedding family/version.
- Postgres schema hiện dùng `create_all`; production hóa cần migration có version.
- Config cần tách rõ local/dev/staging/prod, đặc biệt với base URL, secrets, model names, storage paths.

## Phased Roadmap

### Phase 0: Freeze Baseline

Mục tiêu:
- chốt baseline “đang chạy tốt” để mọi thay đổi sau này đều so sánh được

Việc cần làm:
- tạo commit baseline đầu tiên
- giữ `scripts/smoke_test.sh` là runtime gate tối thiểu
- thêm `Makefile` hoặc `justfile` cho các lệnh chuẩn: `test`, `smoke`, `up`, `down`, `logs`

Exit criteria:
- `uv run pytest -q` pass
- `bash scripts/smoke_test.sh` pass
- `make help`, `make test`, `make smoke`, `make ps` usable as the standard local operator workflow
- có một baseline commit/tag để rollback cục bộ

### Phase 1: Reliability And Config Hardening

Mục tiêu:
- làm cho hệ thống dễ chạy lại, dễ cấu hình, ít lỗi môi trường hơn

Việc cần làm:
- chuẩn hóa `.env` theo môi trường: local, docker, staging
- thêm startup validation cho config quan trọng
- thêm health checks chi tiết hơn cho dependency readiness
- làm rõ timeout/retry policy cho `httpx` gọi `llama.cpp`
- thêm graceful handling khi LLM/embedding unavailable

Exit criteria:
- app fail fast khi config sai
- health endpoint phân biệt được app sống và dependency sẵn sàng
- lỗi từ model backend không làm API treo hoặc trả 500 mơ hồ

### Phase 2: Security And Access Control

Mục tiêu:
- ngăn hệ thống bị lạm dụng hoặc lộ dữ liệu khi mở ra ngoài máy local

Việc cần làm:
- thêm auth tối thiểu cho API và/hoặc Streamlit gateway
- thêm rate limiting cho chat và upload endpoints
- giới hạn upload size và loại file
- quản lý secret bằng env hoặc secret store, không để hardcode
- rà soát prompt injection và file ingestion boundaries

Exit criteria:
- endpoint ghi dữ liệu không còn public hoàn toàn
- upload và chat có basic abuse protection
- secret handling có policy rõ

### Phase 3: Data And Schema Management

Mục tiêu:
- bỏ phụ thuộc vào schema auto-create và chuẩn hóa lifecycle dữ liệu

Việc cần làm:
- thêm Alembic migrations cho PostgreSQL
- xác định retention cho chat history và uploaded documents
- thêm backup/restore procedure cho Postgres và Qdrant
- chuẩn hóa document identity để tránh duplicate ingest tinh vi
- thiết kế versioning khi thay parser, chunking, embedding

Exit criteria:
- schema thay đổi qua migration có kiểm soát
- có quy trình reindex rõ khi đổi model/dimension
- có backup và restore test được

### Phase 4: Observability And Operations

Mục tiêu:
- khi lỗi xảy ra phải biết lỗi ở đâu và ảnh hưởng bao nhiêu

Việc cần làm:
- thêm structured logging cho API
- gắn request id / conversation id vào log
- thêm metrics cơ bản: latency, error rate, retrieval count, empty retrieval, model timeout
- thêm dashboard và alert tối thiểu
- viết runbook cho các sự cố phổ biến: Qdrant rỗng, Postgres down, llama timeout, reindex mismatch

Exit criteria:
- có thể truy ra một request lỗi từ đầu đến cuối
- operator biết check gì đầu tiên khi chat lỗi
- có tín hiệu cảnh báo trước khi người dùng phản ánh

### Phase 5: Retrieval Quality And Evaluation

Mục tiêu:
- nâng chất lượng legal search/chat từ “dùng được” lên “ổn định và đo được”

Việc cần làm:
- tạo eval set câu hỏi pháp lý mẫu theo luật, điều, khoản, follow-up
- đo retrieval recall, citation precision, groundedness
- cải thiện ranking cho query không dấu, viết tắt, điều/khoản, tên luật
- thêm ingestion cho PDF thật và kiểm tra parser fidelity
- cân nhắc hybrid retrieval rõ ràng hơn thay vì lexical overlap đơn thuần

Exit criteria:
- có benchmark trước/sau cho retrieval
- các regression retrieval được bắt trong CI hoặc pre-release check
- citation hallucination có metric theo dõi

### Phase 6: Delivery And Deployment

Mục tiêu:
- đưa hệ thống từ local Docker sang môi trường chạy ổn định hơn

Việc cần làm:
- thêm CI đầy đủ hơn: lint, tests, smoke, build image
- định nghĩa release process và rollback process
- chuẩn hóa image tagging
- thêm staging environment
- chuẩn hóa persistent volumes và resource sizing cho models

Exit criteria:
- mỗi thay đổi đều đi qua pipeline build/test/smoke
- deploy và rollback là quy trình lặp lại được
- staging phản ánh gần đúng production

### Phase 7: Product And Policy Readiness

Mục tiêu:
- làm sản phẩm đủ rõ ràng để người dùng hiểu giới hạn và cách dùng an toàn

Việc cần làm:
- thêm disclaimer rõ cho use case pháp lý
- thêm UX hiển thị citation, warning, confidence cue tốt hơn
- làm rõ ai được ingest dữ liệu nào
- xác định SLA/SLO nội bộ
- định nghĩa escalation path khi chatbot không đủ căn cứ

Exit criteria:
- người dùng hiểu đây là công cụ tra cứu hỗ trợ, không phải quyết định pháp lý cuối cùng
- operator có policy rõ cho dữ liệu và phản hồi sai

## Non-Goals

- Chưa chuyển sang multi-tenant SaaS hoàn chỉnh.
- Chưa thay Streamlit bằng frontend framework khác nếu chưa có áp lực thực tế.
- Chưa thay `llama.cpp` bằng managed provider mặc định; chỉ chuẩn bị abstraction để có thể đổi sau.
- Chưa tối ưu chi phí/hạ tầng ở mức enterprise trước khi có usage thực.

## Open Questions

- Hệ thống này sẽ phục vụ nội bộ, demo khách hàng, hay public internet?
- Có yêu cầu đăng nhập người dùng cuối hay chỉ cần operator-only access?
- Có cần lưu chat history dài hạn hay chỉ phục vụ ngắn hạn?
- Nguồn dữ liệu pháp lý chính thức sẽ là file curated thủ công hay pipeline crawl/normalize riêng?
- Mức độ chấp nhận sai số của câu trả lời là bao nhiêu, và ai duyệt bộ eval pháp lý?

## Handoff

Trạng thái hiện tại: sẵn sàng đi vào implementation theo Phase 0 và Phase 1 ngay.

Thứ tự khuyến nghị:
1. Tạo commit baseline sạch.
2. Thêm `Makefile` hoặc `justfile` cho workflow chuẩn.
3. Bổ sung readiness/health/config validation.
4. Sau đó mới làm auth, migrations, observability.

Lane tiếp theo phù hợp:
- `tdd-workflow` nếu bắt đầu triển khai từng phase
- `verification-loop` nếu muốn dựng checklist release/runtime verification
