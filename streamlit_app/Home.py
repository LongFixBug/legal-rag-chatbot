import streamlit as st

st.set_page_config(page_title="Chatbot Nghĩa Vụ Quân Sự", page_icon="⚖️", layout="wide")

st.title("Chatbot Luật Nghĩa Vụ Quân Sự")
st.write(
    "Ứng dụng RAG chuyên tra cứu và trả lời câu hỏi về nghĩa vụ quân sự Việt Nam: "
    "độ tuổi nhập ngũ, tạm hoãn, miễn gọi nhập ngũ, khám sức khỏe, cận thị và xử phạt."
)

st.info("Khởi động API trước: `uv run uvicorn app.main:app --reload` rồi mở các trang trong sidebar.")
