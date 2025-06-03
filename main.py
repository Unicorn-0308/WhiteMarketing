import streamlit as st

review_page = st.Page("pages/create_review.py", title="Create Review", icon="📄")
task_page = st.Page("pages/create_task.py", title="Create Task", icon="🎫")
general_page = st.Page("pages/general_chat.py", title="General Chat", icon="🤖")

pg = st.navigation([review_page, task_page, general_page])
st.set_page_config(page_title="White Marketing", page_icon="🎃")
pg.run()