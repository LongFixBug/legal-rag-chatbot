Dữ liệu mẫu trong thư mục này phục vụ demo và test cho chatbot RAG pháp lý.

Hiện corpus có:
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
- khi thêm hoặc thay đổi nguồn dữ liệu, cần gọi lại `POST /api/documents/preload`
