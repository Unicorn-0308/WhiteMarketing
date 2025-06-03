import streamlit as st
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agents.general_agent import setup_graph

# --- Page Configuration ---
# st.set_page_config(
#     layout="wide",
#     page_title="General Chat",
#     page_icon="🤖"
# )

# --- Initialize Session State ---
def init_session_state():
    """Initializes all session state variables."""
    defaults = {
        "config": {
            "recursion_limit": 100,
            "configurable": {"thread_id": uuid.uuid4()}
        },
        "chat_associated_client_id": None,  # Client ID for the current chatting
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Title and Description ---
st.title("🎫 AI-Powered Agent")
st.markdown("Select a Client ID to chat with Bot using LangGraph.")
st.markdown("---")


# --- Initialize and Cache Graph ---
@st.cache_resource
def get_compiled_graphs():
    """Builds and compiles the LangGraph graphs. Cached."""
    print("Building and compiling general graph...")
    general_graph_builder = setup_graph()
    general_graph = general_graph_builder.compile(checkpointer=InMemorySaver())
    print("General Graph compiled successfully.")
    return general_graph

general_graph = get_compiled_graphs()

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("⚙️ Agent Configuration")
    client_ids = ["009", "162", "179"]  # Replace with dynamic loading if needed
    selected_client_id = st.selectbox(
        "Select Client ID:",
        options=client_ids,
        index=0,
        help="Choose the client to chat with Bot."
    )

    if not st.session_state.chat_associated_client_id or st.session_state.chat_associated_client_id != selected_client_id:
        st.session_state.chat_associated_client_id = selected_client_id
        st.session_state.config = {
            "recursion_limit": 100,
            "configurable": {"thread_id": uuid.uuid4()}
        }
        st.rerun()

    st.markdown("---")
    if st.button("Clear Chat History", use_container_width=True, type="primary"):
        st.session_state.config = {
            "recursion_limit": 100,
            "configurable": {"thread_id": uuid.uuid4()}
        }
        st.rerun()

st.header("🤖 General Chat")
st.caption("Ask me anything about your Marketing Business!")

# Display existing messages
for message in general_graph.get_state(st.session_state.config).values.get("messages", []):
    avatar = "🤵" if isinstance(message, HumanMessage) else "🤖"
    with st.chat_message('user' if isinstance(message, HumanMessage) else 'assistant', avatar=avatar):
        st.markdown(message.content, unsafe_allow_html=True)

if selected_client_id:
    st.session_state.chat_associated_client_id = selected_client_id
    # Get user input`
    if query := st.chat_input("What are you curious about?"):
        with st.chat_message("user", avatar="🤵"):
            st.markdown(query)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("The assistant is thinking..."):
                message_placeholder = st.empty()
                response = ''
                for chunk in general_graph.stream({
                    "clientId": st.session_state.chat_associated_client_id,
                    "messages": [HumanMessage(content=query)]
                }, config=st.session_state.config, stream_mode="custom"):
                    response += chunk['delta']
                    message_placeholder.markdown(response, unsafe_allow_html=True)

