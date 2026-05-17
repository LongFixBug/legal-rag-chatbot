import streamlit as st

from streamlit_app.utils import get_documents, ingest_document, preload_samples, reindex_samples, upload_document

st.title("Quản lý văn bản")
left, right = st.columns(2)
with left:
    if st.button("Nạp thêm dữ liệu mẫu"):
        result = preload_samples()
        st.success(f"Đã nạp thêm {result['documents_ingested']} văn bản mẫu.")
with right:
    if st.button("Reindex sạch dữ liệu mẫu"):
        result = reindex_samples()
        st.success(
            f"Đã xoá {result['documents_deleted']} văn bản preload cũ và nạp lại "
            f"{result['documents_ingested']} văn bản sạch."
        )

st.subheader("Nạp file")
uploaded_file = st.file_uploader("Chọn file txt/md/html/pdf", type=["txt", "md", "html", "htm", "pdf"])
upload_title = st.text_input("Tiêu đề cho file upload")
if st.button("Upload file") and uploaded_file is not None and upload_title.strip():
    result = upload_document(upload_title, uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")
    st.success(f"Đã index {result['chunks_indexed']} chunks cho {result['document']['title']}")

st.subheader("Hoặc dán văn bản")
with st.form("ingest_form"):
    title = st.text_input("Tiêu đề văn bản")
    content = st.text_area("Nội dung", height=300)
    submitted = st.form_submit_button("Nạp văn bản")
    if submitted and title.strip() and content.strip():
        result = ingest_document(title, content)
        st.success(f"Đã index {result['chunks_indexed']} chunks cho {result['document']['title']}")

st.subheader("Danh sách văn bản")
for document in get_documents():
    st.markdown(f"**{document['title']}**")
    st.caption(f"Nguồn: {document['source']}")
    st.write(document["summary"])
