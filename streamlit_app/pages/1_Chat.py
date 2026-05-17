import streamlit as st

from streamlit_app.utils import ask_question, create_conversation, delete_conversation, get_conversation_history

st.title("Chat nghĩa vụ quân sự")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

debug_mode = st.sidebar.toggle("Chế độ debug", value=False)
if debug_mode:
    st.sidebar.caption(f"Conversation ID: {st.session_state.conversation_id or 'Chưa tạo'}")

if st.button("Cuộc chat mới"):
    st.session_state.conversation_id = None
    st.rerun()

question = st.text_area(
    "Nhập câu hỏi",
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
