import streamlit as st
from src.agents.review_agent import setup_graph as setup_review_graph
import traceback

# --- Page Configuration ---
# st.set_page_config(
#     layout="wide",
#     page_title="Create Review",
#     page_icon="📄"
# )

# --- Initialize Session State ---
def init_session_state():
    """Initializes all session state variables."""
    defaults = {
        "review_report_content": "",
        "review_client_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Title and Description ---
st.title("📄 AI-Powered Agent")
st.markdown("Select a Client ID to generate a review using LangGraph.")
st.markdown("---")


# --- Initialize and Cache Graph ---
@st.cache_resource
def get_compiled_graphs():
    """Builds and compiles the LangGraph graphs. Cached."""
    print("Building and compiling review graph...")
    review_graph_builder = setup_review_graph()
    review_graph = review_graph_builder.compile()
    print("Review Graph compiled successfully.")
    return review_graph

review_graph = get_compiled_graphs()

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("⚙️ Agent Configuration")
    client_ids = ["009", "162", "179"]  # Replace with dynamic loading if needed
    selected_client_id = st.selectbox(
        "Select Client ID:",
        options=client_ids,
        index=0,
        help="Choose the client to create Review."
    )

st.header("📄 Review Generation")
run_review_button = st.button("🚀 Generate Review", use_container_width=True, key="generate_review_btn")

if run_review_button:
    if selected_client_id:
        st.session_state.review_client_id = selected_client_id  # Store for display consistency
        review_response_holder = st.empty()
        try:
            initial_state = {"clientId": selected_client_id}  # Ensure keys match graph expectations

            final_report_content = ""
            with st.spinner(f"🤖 Generating review for Client ID: {selected_client_id}..."):
                try:
                    stream = review_graph.stream(initial_state, stream_mode='custom')

                    for chunk_data in stream:
                        delta = chunk_data.get('delta', '')
                        final_report_content = final_report_content + str(delta)  # Ensure delta is string
                        review_response_holder.markdown(final_report_content)

                except Exception as e:
                    # Let the caller handle specific error messaging and session state updates
                    raise e

            if final_report_content:
                st.session_state.review_report_content = final_report_content
                st.success(f"Review generated successfully for Client ID: {selected_client_id}!")
                review_response_holder.markdown("")
            else:
                st.session_state.review_report_content = "No review content generated."
                st.warning("The agent finished but produced no review content.")

        except Exception as e:
            st.session_state.review_report_content = f"An error occurred: {str(e)}"
            st.error(f"An error occurred while generating the review: {e}")
            st.text(traceback.format_exc())
    else:
        st.warning("Please select a Client ID to generate a review.")

# Display the last generated review
if st.session_state.review_report_content:
    if st.session_state.review_client_id:
        st.subheader(f"Review for Client ID: {st.session_state.review_client_id}")
    st.markdown(st.session_state.review_report_content)
else:
    st.info("Select a Client ID and click 'Generate Review' to see the output.")

st.markdown("---")
st.caption("LangGraph Agent UI Demo")