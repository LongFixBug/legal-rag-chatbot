import streamlit as st

from streamlit_app.utils import ask_question, create_conversation, delete_conversation, get_conversation_history

st.title("Chat nghĩa vụ quân sự")

SAMPLE_QUESTIONS = (
    "Bao nhiêu tuổi thì được gọi nhập ngũ?",
    "Em đang học đại học có được tạm hoãn nghĩa vụ quân sự không?",
    "Cận thị 3 độ có phải đi nghĩa vụ quân sự không?",
    "Không đi khám nghĩa vụ quân sự bị phạt bao nhiêu?",
    "Nữ có bắt buộc đi nghĩa vụ quân sự không?",
    "Đang tại ngũ mà không đủ sức khỏe có được xuất ngũ sớm không?",
)

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "question_input" not in st.session_state:
    st.session_state.question_input = ""

debug_mode = st.sidebar.toggle("Chế độ debug", value=False)
if debug_mode:
    st.sidebar.caption(f"Conversation ID: {st.session_state.conversation_id or 'Chưa tạo'}")

if st.button("Cuộc chat mới"):
    st.session_state.conversation_id = None
    st.rerun()

st.caption("Chọn câu hỏi mẫu hoặc nhập câu hỏi của bạn. Bot hiện được tối ưu cho pháp luật nghĩa vụ quân sự Việt Nam.")
sample_columns = st.columns(2)
for index, sample_question in enumerate(SAMPLE_QUESTIONS):
    if sample_columns[index % 2].button(sample_question, key=f"sample_question_{index}"):
        st.session_state.question_input = sample_question

question = st.text_area(
    "Nhập câu hỏi",
    key="question_input",
    placeholder="Ví dụ: Em đang học đại học có được tạm hoãn nghĩa vụ quân sự không?",
)
top_k = st.sidebar.slider("Số chunk truy xuất", min_value=1, max_value=6, value=4) if debug_mode else 4

if st.button("Hỏi") and question.strip():
    if st.session_state.conversation_id is None:
        conversation = create_conversation(title=question.strip()[:60])
        st.session_state.conversation_id = conversation["id"]
    result = ask_question(question, top_k=top_k, conversation_id=st.session_state.conversation_id)
    st.session_state.conversation_id = result["conversation_id"]
    st.subheader("Trả lời")
    st.write(result["answer"])
    if result.get("validation_warnings"):
        st.warning("\n".join(result["validation_warnings"]))
    if debug_mode:
        st.caption(f"Confidence: {result.get('confidence', 0):.2f}")
        st.caption(f"Abstained: {result.get('abstained', False)}")
        st.caption(f"History used: {result['history_used']} messages")
        st.caption(f"Retrieved chunks: {result['retrieved_chunks']}")
    st.subheader("Căn cứ")
    for citation in result["citations"]:
        label = f"{citation['title']} - {citation.get('article') or 'đoạn liên quan'}"
        with st.expander(label):
            if debug_mode:
                st.caption(f"Score: {citation['score']}")
            st.write(citation["excerpt"])

if st.session_state.conversation_id:
    st.subheader("Lịch sử hội thoại")
    history = get_conversation_history(st.session_state.conversation_id)
    for item in history:
        label = "Bạn" if item["role"] == "user" else "Trợ lý"
        st.markdown(f"**{label}:** {item['content']}")
    if st.button("Xóa cuộc trò chuyện hiện tại"):
        delete_conversation(st.session_state.conversation_id)
        st.session_state.conversation_id = None
        st.rerun()
