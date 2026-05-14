import streamlit as st

from streamlit_app.utils import search_legal

st.title("Tra cứu nâng cao")
query = st.text_input("Từ khóa", placeholder="Ví dụ: quyền thành lập doanh nghiệp")
article = st.text_input("Lọc theo Điều", placeholder="Ví dụ: Điều 17")

if st.button("Tra cứu") and query.strip():
    result = search_legal(query, article=article or None)
    for item in result["results"]:
        st.markdown(f"**{item['title']} - {item.get('article') or 'Không rõ điều'}**")
        st.caption(f"Score: {item['score']}")
        st.write(item["excerpt"])
