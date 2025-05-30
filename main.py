# app.py
import streamlit as st
from src.agents.review_agent import setup_graph # Assuming your script is langgraph_agent.py
# If ReviewGenState is used for type hinting or direct instantiation, import it too.
# from langgraph_agent import ReviewGenState

# --- Page Configuration ---
st.set_page_config(
    layout="wide",
    page_title="LangGraph Review Agent",
    page_icon="📄"
)

# --- Title and Description ---
st.title("📄 AI-Powered Review Generation Agent")
st.markdown("Select a Client ID to generate a comprehensive review report using LangGraph.")
st.markdown("---")

# --- Initialize and Cache Graph ---
@st.cache_resource
def get_compiled_graph():
    """
    Builds and compiles the LangGraph graph.
    Cached to avoid recompilation on every rerun.
    """
    print("Building and compiling the graph...")
    graph_builder = setup_graph()
    compiled_graph = graph_builder.compile()
    print("Graph compiled successfully.")
    return compiled_graph

compiled_graph = get_compiled_graph()

# --- Sidebar for Inputs (Clean UI) ---
with st.sidebar:
    st.header("⚙️ Agent Configuration")
    client_ids = ["009", "162", "179"]
    selected_client_id = st.selectbox(
        "Select Client ID:",
        options=client_ids,
        index=0, # Default selection
        help="Choose the client for whom to generate the report."
    )

    run_button = st.button("🚀 Generate Report")

# --- Main Area for Output ---
st.header("📝 Generated Report")

if 'last_report' not in st.session_state:
    st.session_state.last_report = ""
if 'last_client_id' not in st.session_state:
    st.session_state.last_client_id = None

if run_button:
    if selected_client_id:
        st.session_state.last_client_id = selected_client_id
        response_holder = st.empty()
        with st.spinner(f"🤖 Generating report for Client ID: {selected_client_id}... This might take a few moments."):
            try:
                # The initial state for your graph needs the 'clientId'
                initial_state = {"clientId": selected_client_id}

                # Invoke the graph
                # Your graph nodes expect a RunnableConfig, but LangGraph passes it implicitly.
                # If you needed to pass specific configuration elements, you'd do it here:
                # from langchain_core.runnables import RunnableConfig
                # configuration = RunnableConfig(configurable={"thread_id": "some_thread_id"})
                # final_state = compiled_graph.invoke(initial_state, configuration=configuration)

                stream = compiled_graph.stream(initial_state, stream_mode='custom')
                report_content = ''
                for chunk in stream:
                    report_content += chunk['delta']
                    response_holder.markdown(report_content)

            except Exception as e:
                st.session_state.last_report = f"An error occurred: {str(e)}"
                st.error(f"An error occurred while generating the report: {e}")
                import traceback
                st.text(traceback.format_exc())


        if report_content:
            # Assuming the relevant message is the first AIMessage
            st.session_state.last_report = report_content
            st.success(f"Report generated successfully for Client ID: {selected_client_id}!")
        else:
            st.session_state.last_report = "No report content found in the agent's response."
            st.error("Failed to generate report: No messages found in the output state.")
        st.rerun()
    else:
        st.warning("Please select a Client ID.")

# Display the last generated report (or current one if just generated)
if st.session_state.last_report:
    if st.session_state.last_client_id:
        st.subheader(f"Report for Client ID: {st.session_state.last_client_id}")
    st.markdown(st.session_state.last_report)
else:
    st.info("Select a Client ID and click 'Generate Report' to see the output.")

st.markdown("---")
st.caption("LangGraph Agent UI Demo")
