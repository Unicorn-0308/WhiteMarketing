# app.py
import tiktoken
import streamlit as st
# If ReviewGenState is used for type hinting or direct instantiation, import it too.
# from langgraph_agent import ReviewGenState

# --- Page Configuration ---
st.set_page_config(
    layout="wide",
    page_title="Tiktoken Count",
    page_icon="🧩"
)

# --- Title and Description ---
st.title("Count Token number by TikToken")
st.markdown("Select a Model name to count Token number for that model.")
st.markdown("---")

# --- Initialize and Cache Graph ---
def get_encoder(name):
    return tiktoken.encoding_for_model(name)

# --- Sidebar for Inputs (Clean UI) ---
with st.sidebar:
    st.header("⚙️ Model Configuration")
    model_names = [
        "gpt-4o",
        "gpt-4.1",
        "gpt-4.1-nano"
    ]
    selected_model_name = st.selectbox(
        "Select Client ID:",
        options=model_names,
        index=0, # Default selection
        help="Choose the model for whom to generate the response."
    )

    run_button = st.button("🚀 Count Tokens")

# --- Main Area for Output ---
st.header("📝 Generated Report")

if 'last_count' not in st.session_state:
    st.session_state.last_count = 0
if 'last_model' not in st.session_state:
    st.session_state.last_model = None

text = st.text_area("Input your whole text.")

if run_button:
    if selected_model_name:
        if 'last_model' not in st.session_state or selected_model_name != st.session_state.last_model:
            st.session_state.last_model = selected_model_name
            st.session_state.encoder = get_encoder(selected_model_name)

        with st.spinner(f"🤖 Count Token numbers for Model: {st.session_state.last_model}... This might take a few seconds."):
            try:
                count = len(st.session_state.encoder.encode(text))

            except Exception as e:
                st.session_state.last_count = f"An error occurred: {str(e)}"
                st.error(f"An error occurred while counting the tokens: {e}")
                import traceback
                st.text(traceback.format_exc())


        if count:
            # Assuming the relevant message is the first AIMessage
            st.session_state.last_count = count
            st.success(f"Token number counted successfully for Model: {selected_model_name}!")
        else:
            st.session_state.last_count = "No report content found in the agent's response."
            st.error("Failed to generate report: No messages found in the output state.")
        # st.rerun()
    else:
        st.warning("Please select a Model name.")

# Display the last generated report (or current one if just generated)
if st.session_state.last_count:
    if st.session_state.last_model:
        st.subheader(f"Token number for model: {st.session_state.last_model}")
    st.markdown(f"# {st.session_state.last_count}")
else:
    st.info("Select a Model Name and click 'Count Tokens' to see the output.")

st.markdown("---")
st.caption("Tiktoken UI Demo")
