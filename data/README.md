Dữ liệu mẫu trong thư mục này phục vụ demo và test cho chatbot RAG pháp lý.

Corpus demo mặc định hiện tập trung vào luật nghĩa vụ quân sự Việt Nam:
- `nghia-vu-quan-su-curated-luat-hop-nhat-80-2025.txt`: bản tóm tắt sạch theo Văn bản hợp nhất 80/VBHN-VPQH năm 2025.
- `nghia-vu-quan-su-curated-suc-khoe-hop-nhat-88-2025.txt`: bản tóm tắt sạch theo Văn bản hợp nhất 88/VBHN-BQP năm 2025.
- `nghia-vu-quan-su-curated-xu-phat-hop-nhat-04-2022.txt`: bản tóm tắt sạch theo Văn bản hợp nhất 04/VBHN-BQP về xử phạt.

Các PDF tải từ nguồn chính thức được lưu tại:
- `data/raw/nghia-vu-quan-su/`

Một số PDF Công báo là dạng scan hoặc có lớp text yếu, nên bản `pdftotext` có thể chỉ chứa header/footer hoặc vỡ layout. Các bản trích xuất thô được đặt trong `data/raw/nghia-vu-quan-su/text-*.txt` hoặc `extracted-*.txt` để đối chiếu, không dùng làm corpus preload.

Lưu ý:
- `data/README.md` chỉ là tài liệu hướng dẫn và đã được loại khỏi `preload`
- Docker/app mặc định dùng `PRELOAD_INCLUDE_PATTERN=nghia-vu-quan-su-curated-*.txt`,
  nên chỉ preload corpus nghĩa vụ quân sự đã được làm sạch cho demo
- khi thêm hoặc thay đổi nguồn dữ liệu, nên gọi `POST /api/documents/reindex`
  để xoá dữ liệu preload cũ rồi nạp lại corpus curated
