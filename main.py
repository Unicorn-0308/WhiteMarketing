from db import mongo_

import streamlit as st
from requests import request
import os, uuid, time

if os.environ.get("LANGGRAPH"):

    review_page = st.Page("_pages/create_review.py", title="Create Review", icon="📄")
    task_page = st.Page("_pages/create_task.py", title="Create Task", icon="🎫")
    general_page = st.Page("_pages/general_chat.py", title="General Chat", icon="🤖")

    pg = st.navigation([review_page, task_page, general_page])
    st.set_page_config(page_title="White Marketing", page_icon="🎃")
    pg.run()

else:
    # --- Page Configuration ---
    st.set_page_config(
        layout="wide",
        page_title="WM Co-Pilot",
        page_icon="🤖"
    )

    # --- Initialize Session State ---
    def init_session_state():
        """Initializes all session state variables."""
        defaults = {
            "sessionId": uuid.uuid4(),
            "messages": [{
                "role": "assistant",
                "content": """Hi there! 👋
My name is Nathan. How can I assist you today?"""
            }]
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value


    init_session_state()

    # --- Title and Description ---
    st.title("🎫 AI-Powered Agent")
    st.markdown("---")
    st.caption("Ask me anything about your Marketing Business!")

    # --- Sidebar for Inputs ---
    with st.sidebar:
        if st.button("Clear Chat History", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.rerun()

    # Display existing messages
    for message in st.session_state.messages:
        avatar = "🤵" if message.get("role", "user") == "user" else "🤖"
        with st.chat_message(message.get("role", "user"), avatar=avatar):
            st.markdown(message.get("content", ""), unsafe_allow_html=True)

    # Get user input`
    # files = st.file_uploader("Upload your KPI data", "csv", True, label_visibility="hidden")
    if prompt := st.chat_input("What are you curious about?", accept_file="multiple", file_type="csv"):
        if prompt.text:
        # if prompt := st.chat_input("What are you curious about?"):
            with st.chat_message("user", avatar="🤵"):
                st.markdown(prompt.text, unsafe_allow_html=True)
            st.session_state.messages.append({"role": "user", "content": prompt.text})

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("The assistant is thinking..."):
                    files_to_send = {}
                    for f in prompt.files or []:
                        files_to_send[f.name] = (f.name, f.getvalue(), "text/csv")

                    response = request(
                        "post",
                        "https://whitemarketing.app.n8n.cloud/webhook/3af16ffd-ac9f-4a13-93d9-4bdffe3d949c",
                        data={
                            "action": "sendMessage",
                            "chatInput": prompt.text,
                            "sessionId": st.session_state.sessionId,
                        },
                        files=files_to_send,
                        timeout=300,
                    )

                    execution = response.json()

                    result = {}
                    out = 0
                    while True:
                        result = mongo_.find_one({"id": execution["id"]})
                        if result or out > 60:
                            break
                        time.sleep(5)
                        out += 1

                    try:
                        st.markdown(result.get("output", ""), unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": result.get("output", "")})
                        mongo_.delete_one({"id": execution["id"]})
                        st.rerun()
                    except Exception as e:
                        st.markdown(str(e), unsafe_allow_html=True)


