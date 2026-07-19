import streamlit as st
from agent import chat_stream, MODEL

st.set_page_config(
    page_title="OpenClaw Agent",
    page_icon="🦞",
    layout="centered",
)

st.title("🦞 OpenClaw Agent")
st.caption(f"Модель: `{MODEL}` · Работает 24/7 на Streamlit Cloud")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Спросите OpenClaw..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]
        response = st.write_stream(chat_stream(prompt, history))

    st.session_state.messages.append({"role": "assistant", "content": response})

with st.sidebar:
    st.header("⚙️ Информация")
    st.text(f"Модель: {MODEL}")
    st.text("Хостинг: Streamlit Cloud")
    st.text("Статус: 🟢 Online")
    if st.button("🗑️ Очистить чат"):
        st.session_state.messages = []
        st.rerun()