import streamlit as st
from streamlit_theme import st_theme
from src.agents.task_agent import setup_graph as setup_task_graph
from src.models.task import Task
import traceback
import markdown

# --- Page Configuration ---
# st.set_page_config(
#     layout="wide",
#     page_title="Create Task",
#     page_icon="🎫"
# )

# --- Initialize Session State ---
def init_session_state():
    """Initializes all session state variables."""
    defaults = {
        "task_details_content": "",  # For the final generated task details
        "task": None,
        "task_associated_client_id": None,  # Client ID for the last task
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Title and Description ---
st.title("🎫 AI-Powered Agent")
st.markdown("Select a Client ID to describe a task using LangGraph.")
st.markdown("---")


# --- Initialize and Cache Graph ---
@st.cache_resource
def get_compiled_graphs():
    """Builds and compiles the LangGraph graphs. Cached."""
    print("Building and compiling task graph...")
    task_graph_builder = setup_task_graph()
    task_graph = task_graph_builder.compile()
    print("Task Graph compiled successfully.")
    return task_graph

task_graph = get_compiled_graphs()

# --- HTML & CSS for the Card ---
HTML_CARD_TEMPLATE = """
<div class="{card_class}">
    <div class="{header_class}">
        <h2>{name}</h2>
    </div>
    <div class="{body_class}">
        <div class="{meta_class}">
            <p><strong>Assignee:</strong> {assignee}</p>
            <p><strong>Due On:</strong> {due_on}</p>
            <p><strong>Section:</strong> {section}</p>
        </div>

        {notes_html}

        {tags_html}

        {custom_fields_html}
    </div>
</div>

<style>
    /* --- Base Styles (Common for Light & Dark where applicable) --- */
    .task-card, .task-card-dark {{
        border-radius: 12px;
        margin-bottom: 20px;
        padding: 20px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }}
    .task-card:hover, .task-card-dark:hover {{
        transform: translateY(-5px);
    }}

    .task-header h2, .task-header-dark h2 {{
        margin-top: 0;
        margin-bottom: 15px;
        font-size: 1.6em;
        padding-bottom: 10px;
    }}

    .task-body p, .task-body-dark p {{
        margin: 5px 0;
        line-height: 1.6;
    }}

    .task-meta p strong, .task-meta-dark p strong {{
        min-width: 100px; /* Align values somewhat */
        display: inline-block;
    }}

    .task-notes-section, .task-tags-section, .custom-fields-section {{
        margin-top: 15px;
        padding-top: 15px;
    }}
    .task-notes-section h4, .task-tags-section h4, .custom-fields-section h4 {{
        margin-top: 0;
        margin-bottom: 8px;
    }}

    .tag-item {{ /* Tag styling is often distinct and might not need much theme change */
        display: inline-block;
        background-color: #3498db; /* Asana-like blue */
        color: white;
        padding: 5px 12px;
        margin-right: 8px;
        margin-bottom: 8px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: 500;
    }}
    .tag-item-dark {{ /* Example if you wanted a slightly different tag for dark */
        display: inline-block;
        background-color: #2980b9; /* Slightly darker blue for dark mode */
        color: #f0f0f0;
        padding: 5px 12px;
        margin-right: 8px;
        margin-bottom: 8px;
        border-radius: 15px;
        font-size: 0.85em;
        font-weight: 500;
    }}


    /* --- Light Theme Specific Styles --- */
    .task-card {{
        background-color: #ffffff;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
        color: #333;
        border: 1px solid #e0e0e0; /* Subtle border for light */
    }}
    .task-card:hover {{
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
    }}
    .task-header h2 {{
        color: #2c3e50; /* Dark blue-gray */
        border-bottom: 2px solid #ecf0f1; /* Light gray separator */
    }}
    .task-body p {{
        color: #333;
    }}
    .task-meta p strong {{
        color: #555;
    }}
    .task-notes-section, .task-tags-section, .custom-fields-section {{
        border-top: 1px solid #eee;
    }}
    .task-notes-section h4, .task-tags-section h4, .custom-fields-section h4 {{
        color: #34495e; /* Slightly darker blue-gray */
    }}
    .task-notes-content {{
        background-color: #f9f9f9;
        padding: 10px;
        border-radius: 6px;
        white-space: pre-wrap; /* Preserve line breaks in notes */
        font-size: 0.95em;
        color: #444;
    }}
    .custom-field-item {{
        background-color: #f0f0f0;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 8px;
        font-size: 0.9em;
        color: #333;
    }}
    .custom-field-item strong {{
        color: #2c3e50;
    }}

    /* --- Dark Theme Specific Styles --- */
    .task-card-dark {{
        background-color: #262730; /* Dark background - common for Streamlit dark */
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4); /* More pronounced shadow for dark */
        color: #fafafa; /* Light text color */
        border: 1px solid #31333F; /* Subtle border for definition */
    }}
    .task-card-dark:hover {{
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.5);
    }}
    .task-header-dark h2 {{
        color: #e1e3e6; /* Lighter header text */
        border-bottom: 2px solid #31333F; /* Darker separator */
    }}
    .task-body-dark p {{
        color: #c5c7d1; /* Slightly softer light text for body */
    }}
    .task-meta-dark p strong {{
        color: #a0a8b5; /* Lighter strong text */
    }}
    .task-notes-section-dark, .task-tags-section-dark, .custom-fields-section-dark {{
        border-top: 1px solid #31333F; /* Darker separator */
    }}
    .task-notes-section-dark h4, .task-tags-section-dark h4, .custom-fields-section-dark h4 {{
        color: #b0b8c5; /* Lighter section headers */
    }}
    .task-notes-content-dark {{
        background-color: #1e1f26; /* Even darker for note background */
        padding: 10px;
        border-radius: 6px;
        white-space: pre-wrap;
        font-size: 0.95em;
        color: #d1d3d9;
    }}
    .custom-field-item-dark {{
        background-color: #31333F; /* Darker custom field background */
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 8px;
        font-size: 0.9em;
        color: #c5c7d1;
    }}
    .custom-field-item-dark strong {{
        color: #e1e3e6;
    }}
</style>

"""
def format_task_as_html(task: Task) -> str:
    """Formats a Task object into an HTML card, adapting to detected theme."""

    # Detect current theme using a component
    current_theme_data = st_theme() # Use a unique key if calling multiple times
    is_dark_theme = current_theme_data and current_theme_data.get('base') == 'dark'

    card_class = "task-card-dark" if is_dark_theme else "task-card"
    header_class = "task-header-dark" if is_dark_theme else "task-header"
    body_class = "task-body-dark" if is_dark_theme else "task-body"
    meta_class = "task-meta-dark" if is_dark_theme else "task-meta"
    notes_section_class = "task-notes-section-dark" if is_dark_theme else "task-notes-section"
    notes_content_class = "task-notes-content-dark" if is_dark_theme else "task-notes-content"
    tags_section_class = "task-tags-section-dark" if is_dark_theme else "task-tags-section"
    tag_item_class = "tag-item-dark" if is_dark_theme else "tag-item" # Example if tags need different style
    custom_fields_section_class = "custom-fields-section-dark" if is_dark_theme else "custom-fields-section"
    custom_field_item_class = "custom-field-item-dark" if is_dark_theme else "custom-field-item"


    notes_html = ""
    if task.notes:
        notes_html = f"""
        <div class="{notes_section_class}">
            <h4>Notes:</h4>
            <div class="{notes_content_class}" markdown="1">{markdown.markdown(task.notes)}</div>
        </div>
        """

    tags_html = ""
    if task.tags:
        tag_items_html = "".join([f'<span class="{tag_item_class}">{tag}</span>' for tag in task.tags])
        tags_html = f"""
        <div class="{tags_section_class}">
            <h4>Tags:</h4>
            <div>{tag_items_html}</div>
        </div>
        """

    custom_fields_html = ""
    if task.custom_fields:
        cf_items_html = "".join([
            f'<div class="{custom_field_item_class}"><strong>{cf.name}:</strong> {cf.value}</div>'
            for cf in task.custom_fields
        ])
        custom_fields_html = f"""
        <div class="{custom_fields_section_class}">
            <h4>Custom Fields:</h4>
            {cf_items_html}
        </div>
        """

    return HTML_CARD_TEMPLATE.format(
        card_class=card_class,
        header_class=header_class,
        body_class=body_class,
        meta_class=meta_class,
        name=task.name if task.name else "Untitled Task",
        assignee=task.assignee if task.assignee else "N/A",
        due_on=task.due_on if task.due_on else "N/A",
        section=task.section if task.section else "N/A",
        notes_html=notes_html,
        tags_html=tags_html,
        custom_fields_html=custom_fields_html
    )

# --- Sidebar for Inputs ---
with st.sidebar:
    st.header("⚙️ Agent Configuration")
    client_ids = ["009", "162", "179"]  # Replace with dynamic loading if needed
    selected_client_id = st.selectbox(
        "Select Client ID:",
        options=client_ids,
        index=0,
        help="Choose the client to create Task."
    )

st.header("🎫 Task Generation")
task_description = st.text_input(
    "Input description for the new task:",
    key="task_description_input",
)

run_task_button = st.button(
    "🚀 Generate Task",
    use_container_width=True,
    key="generate_task_btn",
    disabled=not task_description.strip()  # Disable if description is empty
)

if run_task_button:  # Triggered by button click now
    if selected_client_id and task_description.strip():
        st.session_state.task_associated_client_id = selected_client_id  # Store for display
        task_response_holder = st.empty()  # For final streamed task details

        try:
            # Ensure keys match your task_graph's expected input state
            initial_state = {"clientId": selected_client_id, "description": task_description}

            final_task_content = ""
            with st.spinner(f"🤖 Generating task for Client ID: {selected_client_id}..."):
                try:
                    stream = task_graph.stream(initial_state, stream_mode='custom')

                    for chunk_data in stream:
                        if chunk_data.get('position') == 'final_response':
                            delta = chunk_data.get('delta', '')
                            final_task_content = final_task_content + str(delta)
                            task_response_holder.markdown(final_task_content)
                        else:
                            task_info = chunk_data.get('task', '')
                            if task_info:  # Only display if there's task info
                                st.session_state.task = task_info
                except Exception as e:
                    # Let the caller handle specific error messaging and session state updates
                    raise e

            if final_task_content:  # final_task_content is the accumulated 'final_response'
                st.session_state.task_details_content = final_task_content
                st.success(f"Task details generated successfully for Client ID: {selected_client_id}!")
                task_response_holder.markdown("")
            else:
                st.session_state.task_details_content = "No final task details generated by the agent."
                st.warning(
                    "The agent finished processing but produced no final task details. Intermediate steps might have been shown above.")

        except Exception as e:
            st.session_state.task_details_content = f"An error occurred: {str(e)}"
            st.error(f"An error occurred while generating the task: {e}")
            st.text(traceback.format_exc())
    else:
        if not selected_client_id:
            st.warning("Please select a Client ID.")
        if not task_description.strip():
            st.warning("Please enter a task description.")

# Display the last generated task details
if st.session_state.task_details_content and st.session_state.task:
    if st.session_state.task_associated_client_id:
        st.subheader(f"Generated Task for Client ID: {st.session_state.task_associated_client_id}")
    st.markdown(st.session_state.task_details_content)  # Display final task content
    st.html(format_task_as_html(st.session_state.task))
else:
    st.info("Enter a task description, select a Client ID, and click 'Generate Task' to see the output.")

st.markdown("---")
st.caption("LangGraph Agent UI Demo")