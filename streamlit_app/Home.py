import streamlit as st

st.set_page_config(page_title="RAG Legal Assistant", page_icon="⚖️", layout="wide")

st.title("RAG Legal Assistant")
st.write(
    "Ứng dụng tra cứu văn bản pháp luật theo mô hình RAG. "
    "Backend chạy trên FastAPI, dữ liệu được chunk theo Điều/Khoản để giữ citation rõ ràng."
)

st.info("Khởi động API trước: `uv run uvicorn app.main:app --reload` rồi mở các trang trong sidebar.")
