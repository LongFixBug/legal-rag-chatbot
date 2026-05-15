Dữ liệu mẫu trong thư mục này phục vụ demo và test cho chatbot RAG pháp lý.

Corpus demo mặc định hiện tập trung vào luật nghĩa vụ quân sự:
- `nghia-vu-quan-su-2015.txt`
- `nghia-vu-quan-su-kham-suc-khoe-105-2023.txt`
- `nghia-vu-quan-su-xu-phat-120-2013-37-2022.txt`

Các file cũ vẫn được giữ để test hồi quy và tham khảo kỹ thuật:
- các văn bản pháp luật mẫu ban đầu để test luồng RAG
- bộ thuế thu nhập cá nhân cho người lao động:
  `Luật 109/2025/QH15`, `Nghị quyết 110/2025/UBTVQH15`,
  `VBHN 04/2007/QH12 + 26/2012/QH13`, `Nghị định 65/2013/NĐ-CP`,
  `Thông tư 111/2013/TT-BTC`

Importer hỗ trợ nạp lại bộ văn bản thuế từ nguồn chính thức:

```bash
uv run python scripts/import_worker_tax_docs.py
```

Lưu ý:
- `data/README.md` chỉ là tài liệu hướng dẫn và đã được loại khỏi `preload`
- Docker/app mặc định dùng `PRELOAD_INCLUDE_PATTERN=nghia-vu-quan-su*.txt`,
  nên chỉ preload corpus nghĩa vụ quân sự cho demo
- khi thêm hoặc thay đổi nguồn dữ liệu, cần gọi lại `POST /api/documents/preload`
