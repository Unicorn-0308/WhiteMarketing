import json, os, time, threading, copy, re
# import asana
# from asana.rest import ApiException
from openai import OpenAI
client = OpenAI()

# configuration = asana.Configuration()
# configuration.access_token = "2/1210174643501342/1210316415011274:11432dbf64383536966062c64013f318"
# api_client = asana.ApiClient(configuration)

# lock = threading.Lock()
# threads = []
# next_t = 30

def load():
    space = {
        # 'updated': ['again'],
        # 'again': [],
    }
    file_names = os.listdir("MVP_data/asana")
    for name in file_names:
        try:
            data = json.load(open(f"MVP_data/asana/{name}", 'r'))
            space[name.split('.json')[0]] = data
        except Exception as e:
            print(name)
    return space

def save(origin_space):
    # with lock:
    space = copy.deepcopy(origin_space)
    for key in space['updated']:
        json.dump(space[key], open(f"MVP_data/asana/{key}.json", 'w'), indent=4)
        print(f"Saved {key}.json")
    space['updated'] = []

# For more robust HTML stripping from 'html_notes' if needed:
# You might need to install it: pip install beautifulsoup4
# from bs4 import BeautifulSoup


from datetime import datetime
import html # In case html_notes actually contains useful text and not just <body></body>

def format_date(date_str, default="not set"):
    """Helper function to format ISO date strings or return a default."""
    if not date_str:
        return default
    try:
        dt_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt_obj.strftime("%B %d, %Y")
    except ValueError:
        return default # Or handle error as needed

def extract_names(entity_list, default_if_empty="none assigned"):
    """Helper function to extract names from a list of Asana entities (users, etc.)."""
    if not entity_list:
        return default_if_empty
    names = [entity.get("name", "Unknown") for entity in entity_list]
    if not names:
        return default_if_empty
    if len(names) == 1:
        return names[0]
    elif len(names) == 2:
        return " and ".join(names)
    else:
        return ", ".join(names[:-1]) + ", and " + names[-1]

def clean_html_notes(html_notes_str):
    """
    Basic HTML cleaner. Removes <body></body> and other common simple tags.
    For more complex HTML, a library like BeautifulSoup would be better.
    """
    if not html_notes_str:
        return ""
    # Remove body tags
    text = re.sub(r'<body[^>]*>(.*?)</body>', r'\1', html_notes_str, flags=re.IGNORECASE | re.DOTALL)
    # Remove other common HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Replace common HTML entities
    text = text.replace(' ', ' ').replace('&', '&').replace('<', '<').replace('>', '>')
    return text.strip()


def get_project_description(project_data):
    """
    Converts Asana project JSON description into a human-readable text description.
    """
    if not isinstance(project_data, dict):
        return "Invalid project description format."

    # --- Basic Information ---
    name = project_data.get("name", "Unnamed Project")
    description_parts = [f"Project Name: {name}."]

    status = "archived" if project_data.get("archived") else "active"
    completion = "completed" if project_data.get("completed") else "ongoing"
    description_parts.append(f"It is currently {status} and {completion}.")

    if project_data.get("completed") and project_data.get("completed_at"):
        description_parts.append(f"It was completed on {format_date(project_data.get('completed_at'))}.")

    # --- Ownership and Team ---
    try:
        owner_name = project_data.get("owner", {})
        if owner_name == None:
            owner_name = 'N/A'
        else:
            owner_name = owner_name.get("name", "N/A")
        if owner_name != "N/A":
            description_parts.append(f"The project is owned by {owner_name}.")
    except AttributeError:
        print(project_data.get("owner", {}))

    team_name = project_data.get("team", {}).get("name", "N/A")
    if team_name != "N/A":
        description_parts.append(f"It belongs to the '{team_name}' team.")

    workspace_name = project_data.get("workspace", {}).get("name", "N/A")
    if workspace_name != "N/A":
        description_parts.append(f"It is part of the '{workspace_name}' workspace.")

    # --- Dates ---
    created_at = format_date(project_data.get("created_at"))
    modified_at = format_date(project_data.get("modified_at"))
    description_parts.append(f"Created on {created_at}, last modified on {modified_at}.")

    due_date = format_date(project_data.get("due_date") or project_data.get("due_on"))
    start_date = format_date(project_data.get("start_on"))

    if due_date != "not set" and start_date != "not set":
        description_parts.append(f"The project is scheduled to run from {start_date} to {due_date}.")
    elif due_date != "not set":
        description_parts.append(f"It is due on {due_date}.")
    elif start_date != "not set":
        description_parts.append(f"It is scheduled to start on {start_date}.")

    # --- People ---
    members = extract_names(project_data.get("members"))
    description_parts.append(f"Project members include: {members}.")

    followers = extract_names(project_data.get("followers"))
    description_parts.append(f"It is being followed by: {followers}.")

    # --- Custom Fields ---
    custom_field_settings = project_data.get("custom_field_settings", [])
    if custom_field_settings:
        cf_descriptions = []
        for setting in custom_field_settings:
            field = setting.get("custom_field", {})
            field_name = field.get("name")
            field_type = field.get("resource_subtype", field.get("type")) # "enum", "number", "text", etc.

            if field_name:
                cf_desc = f"'{field_name}' ({field_type})"
                if field_type == "enum" and field.get("enum_options"):
                    options = [opt.get("name") for opt in field.get("enum_options", []) if opt.get("name")]
                    if options:
                        cf_desc += f" with options: {', '.join(options)}"
                elif field_type == "number" and field.get("precision") is not None:
                     cf_desc += f" with precision {field.get('precision')}"
                cf_descriptions.append(cf_desc)

        if cf_descriptions:
            description_parts.append(f"The project utilizes the following custom fields: {'; '.join(cf_descriptions)}.")
    else:
        description_parts.append("No custom fields are specifically configured for this project.")

    # --- Notes ---
    notes = project_data.get("notes", "").strip()
    html_notes_cleaned = clean_html_notes(project_data.get("html_notes", ""))

    project_description = ""
    if notes:
        project_description = notes
    elif html_notes_cleaned: # Use cleaned HTML notes if regular notes are empty
        project_description = html_notes_cleaned

    if project_description:
        description_parts.append(f"Project Description/Notes: {project_description}")
    else:
        description_parts.append("There are no specific notes or description provided for this project.")

    # --- Other Details ---
    color = project_data.get("color", "default")
    if color and color != "none": # Asana uses "none" for no color
         description_parts.append(f"The project is visually represented with a '{color}' color.")

    privacy = project_data.get("privacy_setting", "unknown")
    description_parts.append(f"Its privacy setting is '{privacy}'.")

    permalink = project_data.get("permalink_url")
    if permalink:
        description_parts.append(f"More details can be found at its Asana page: {permalink}.")

    if project_data.get("created_from_template"):
        template_info = project_data.get("created_from_template", {})
        template_name = template_info.get("name", "an unspecified template") # Assuming template might have a name
        description_parts.append(f"This project was created from {template_name}.")


    return " ".join(description_parts)

def get_attachment_description(attachment_data):
    """
    Converts Asana attachment JSON description into a human-readable text description.
    Assumes format_date_string is defined and available.
    """
    if not isinstance(attachment_data, dict):
        return "Invalid attachment description format."

    description_parts = []

    name = attachment_data.get("name", "Unnamed attachment")
    created_at_str = format_date(attachment_data.get("created_at"), "an unknown date")
    host = attachment_data.get("host", "an external source")
    attachment_type = attachment_data.get("resource_subtype", "file") # e.g., "asana", "dropbox_file"

    parent_info = attachment_data.get("parent", {})
    parent_name = parent_info.get("name", "an unspecified parent item")
    parent_type = parent_info.get("resource_type", "item") # e.g., "task", "project"
    # resource_subtype for parent (e.g. "default_task") can be used for more specificity if needed
    # parent_resource_subtype = parent_info.get("resource_subtype", "")

    # Sentence 1: File name and type/host
    if host.lower() == "asana" and attachment_type.lower() == "asana":
        description_parts.append(f"The file named '{name}' was uploaded directly to Asana.")
    else:
        description_parts.append(f"The attachment '{name}' is a {attachment_type} file hosted by {host}.")

    # Sentence 2: Creation date and parent
    description_parts.append(f"It was added on {created_at_str} to the {parent_type} titled '{parent_name}'.")

    # Sentence 3: Accessibility
    if attachment_data.get("permanent_url"):
        description_parts.append(f"This attachment can be viewed or downloaded via its permanent link in Asana.")
    elif attachment_data.get("view_url") or attachment_data.get("download_url"):
        # Fallback if permanent_url is not present but others are (less ideal for long-term linking)
        description_parts.append(f"A link to view or download this attachment is available.")
    else:
        description_parts.append(f"Access details for this attachment are not specified.")


    return " ".join(description_parts)


def get_custom_field_description(custom_field_data):
    """
    Converts Asana Custom Field JSON description into a human-readable text description.
    GIDs are excluded from the output.
    """
    if not isinstance(custom_field_data, dict):
        return "Invalid custom field description format."

    description_parts = []

    name = custom_field_data.get("name", "Unnamed Custom Field")
    # Use resource_subtype as the primary type, fallback to type
    field_type = custom_field_data.get("resource_subtype", custom_field_data.get("type", "unknown type"))

    description_parts.append(f"The custom field is named '{name}' and is a '{field_type}' type field.")

    # Description
    field_description = custom_field_data.get("description", "").strip()
    if field_description:
        description_parts.append(f"Its purpose is described as: \"{field_description}\".")

    # Creator / Asana-created field
    created_by_info = custom_field_data.get("created_by")
    asana_created_field_type = custom_field_data.get("asana_created_field")  # e.g., "minutes", "story_points"

    if asana_created_field_type:
        description_parts.append(
            f"This is a standard Asana-managed field, often used for tracking '{asana_created_field_type}'.")
    elif created_by_info and created_by_info.get("name"):
        creator_name = created_by_info.get("name")
        description_parts.append(f"It was created by {creator_name}.")
    elif created_by_info:  # created_by object exists but no name
        description_parts.append("It was created by an unnamed user.")
    else:  # created_by is null and not an asana_created_field
        description_parts.append("The creator of this field is not specified.")

    # Type-specific details
    if field_type in ["enum", "multi_enum"]:
        enum_options_list = custom_field_data.get("enum_options", [])
        if enum_options_list:
            # Filter for enabled options that have a name
            option_names = [
                opt.get("name") for opt in enum_options_list if opt.get("name") and opt.get("enabled", False)
                # Default to False if 'enabled' not present
            ]
            if option_names:
                options_str = ""
                if len(option_names) == 1:
                    options_str = f"'{option_names[0]}'"
                elif len(option_names) == 2:
                    options_str = f"'{option_names[0]}' and '{option_names[1]}'"
                else:
                    quoted_options = [f"'{name}'" for name in option_names]
                    options_str = ", ".join(quoted_options[:-1]) + ", and " + quoted_options[-1]

                if field_type == "multi_enum":
                    description_parts.append(
                        f"It allows selection of one or more values from the available options: {options_str}.")
                else:  # enum
                    description_parts.append(f"Possible values include: {options_str}.")
            else:
                description_parts.append(
                    "It is an enum/multi-enum field but currently has no enabled options with names defined.")
        else:
            description_parts.append("It is an enum/multi-enum field but has no options specified.")

        # Notifications for enum/multi-enum
        notifications_enabled = custom_field_data.get("has_notifications_enabled", False)
        if notifications_enabled:
            description_parts.append("Notifications are enabled for changes to this field.")
        else:
            description_parts.append("Notifications are not enabled for changes to this field.")


    elif field_type == "number":
        precision = custom_field_data.get("precision")
        if precision is not None:  # precision can be 0
            description_parts.append(
                f"It stores numbers and is configured with {precision} decimal places of precision.")
        else:
            description_parts.append("It stores numbers, but its specific precision is not detailed.")

    elif field_type == "text":
        description_parts.append("It is designed to hold textual information.")

    # Add more elif blocks here for other field_types like 'people', 'date', 'boolean' if needed.

    # Formula field
    is_formula = custom_field_data.get("is_formula_field", False)
    if is_formula:
        description_parts.append("This field's value is calculated based on a formula.")

    # Global vs. Local Scope
    is_global = custom_field_data.get("is_global_to_workspace", False)
    scope_description = "available across the entire workspace" if is_global else "configured for specific MVP_data/asana or portfolios"

    # Privacy Setting
    privacy = custom_field_data.get("privacy_setting", "unknown")
    privacy_friendly = privacy.replace("_", " ")  # e.g., "public with guests"

    description_parts.append(f"The field is {scope_description}, and its privacy is set to '{privacy_friendly}'.")

    return " ".join(description_parts)

def get_project_template_description(template_data):
    """
    Converts Asana Project Template JSON description into a human-readable text description.
    Assumes clean_html_notes and extract_names functions are defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(template_data, dict):
        return "Invalid project template description format."

    description_parts = []

    name = template_data.get("name", "Unnamed Project Template")
    description_parts.append(f"This is a project template named '{name}'.")

    # Owner
    owner_info = template_data.get("owner", {})
    owner_name = owner_info.get("name")
    if owner_name:
        description_parts.append(f"It is owned by {owner_name}.")
    else:
        description_parts.append("The owner of this template is not specified.")

    # Team
    team_info = template_data.get("team", {})
    team_name = team_info.get("name")
    if team_name:
        description_parts.append(f"It is associated with the '{team_name}' team.")
    else:
        description_parts.append("It is not explicitly associated with any team.")

    # Description
    template_description_text = template_data.get("description", "").strip()
    if not template_description_text:
        # Fallback to cleaned HTML description if plain description is empty
        html_desc = template_data.get("html_description", "")
        # Assuming clean_html_notes function is available from previous context
        template_description_text = clean_html_notes(html_desc)

    if template_description_text:
        description_parts.append(f"The template's description is: \"{template_description_text}\".")
    else:
        description_parts.append("No specific description is provided for this template.")

    # Public status
    is_public = template_data.get("public", False) # Default to False if not present
    public_status = "publicly available" if is_public else "private"
    description_parts.append(f"This template is {public_status}.")

    # Color
    color = template_data.get("color") # Can be null
    if color and color.lower() != "none": # Asana uses "none" or null for no color
        description_parts.append(f"It is visually marked with a '{color}' color.")
    else:
        description_parts.append("No specific color is assigned to this template.")

    # Requested Dates
    requested_dates_list = template_data.get("requested_dates", [])
    if requested_dates_list:
        date_requests_summary = []
        for req_date in requested_dates_list:
            date_name = req_date.get("name")
            date_desc = req_date.get("description")
            if date_name and date_desc:
                date_requests_summary.append(f"'{date_name}' (for: {date_desc})")
            elif date_name:
                date_requests_summary.append(f"'{date_name}'")
        if date_requests_summary:
            description_parts.append(f"When creating a project from this template, the following date inputs are prompted: {', '.join(date_requests_summary)}.")
    else:
        description_parts.append("This template does not prompt for specific dates during project creation.")

    # Requested Roles
    requested_roles_list = template_data.get("requested_roles", [])
    if requested_roles_list:
        # Assuming extract_names is available and suitable for a list of role objects with a "name" key
        role_names = extract_names(requested_roles_list, default_if_empty="")
        if role_names:
            description_parts.append(f"The template can prompt for assignment of roles such as: {role_names}.")
        else:
            description_parts.append("The template may prompt for roles, but specific role names are not detailed or none are configured.")
    else:
        description_parts.append("This template does not prompt for specific role assignments during project creation.")

    return " ".join(description_parts)

def get_section_description(section_data):
    """
    Converts Asana Section JSON description into a human-readable text description.
    Assumes format_date_string function is defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(section_data, dict):
        return "Invalid section description format."

    description_parts = []

    section_name = section_data.get("name", "Unnamed Section")
    created_at_str = format_date(section_data.get("created_at"), "an unknown date") # Assuming format_date_string is available

    project_info = section_data.get("project", {})
    project_name = project_info.get("name", "an unspecified project")

    # Sentence 1: Basic information about the section
    description_parts.append(f"This is a section named '{section_name}'.")

    # Sentence 2: Context within a project
    description_parts.append(f"It is part of the project '{project_name}'.")

    # Sentence 3: Creation date
    description_parts.append(f"The section was created on {created_at_str}.")

    # Combine into a more narrative form if preferred, or keep as separate facts.
    # Example of a more combined narrative:
    # return (f"The section '{section_name}' was created on {created_at_str} "
    #         f"within the project '{project_name}'.")

    return " ".join(description_parts)

def get_status_update_description(status_data):
    """
    Converts Asana Status Update JSON description into a human-readable text description.
    Assumes format_date_string and clean_html_notes functions are defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(status_data, dict):
        return "Invalid status update description format."

    description_parts = []

    # Parent item information
    parent_info = status_data.get("parent", {})
    parent_name = parent_info.get("name", "an unspecified item")
    parent_resource_type = parent_info.get("resource_type", "item") # project, portfolio, goal

    # Determine item type more specifically from resource_subtype if available
    resource_subtype = status_data.get("resource_subtype", "")
    item_type_description = parent_resource_type # Default to parent's resource_type

    if "project_status_update" in resource_subtype:
        item_type_description = "project"
    elif "portfolio_status_update" in resource_subtype:
        item_type_description = "portfolio"
    elif "goal_status_update" in resource_subtype:
        item_type_description = "goal"
    # If resource_subtype isn't specific but parent_resource_type is, it's already set

    # Creator information
    creator_info = status_data.get("created_by", {})
    creator_name = creator_info.get("name", "an unknown user")

    description_parts.append(f"This is a status update for the {item_type_description} '{parent_name}', provided by {creator_name}.")

    # Status type
    status_type_raw = status_data.get("status_type", "unknown")
    status_type_map = {
        "on_track": "On Track",
        "at_risk": "At Risk",
        "off_track": "Off Track",
        "on_hold": "On Hold",
        "complete": "Complete",
        # Goal-specific statuses (if applicable, based on resource_subtype)
        "upcoming": "Upcoming",
        "active": "Active", # Can also be a generic status
        "achieved": "Achieved",
        "partial": "Partially Achieved", # Could also be "Partial"
        "missed": "Missed",
        "dropped": "Dropped",
    }
    status_type_friendly = status_type_map.get(status_type_raw.lower(), status_type_raw.replace("_", " ").title())

    # Date information
    created_at_iso = status_data.get("created_at")
    modified_at_iso = status_data.get("modified_at")

    formatted_created_at = format_date(created_at_iso, "") # Assumes format_date_string is available
    formatted_modified_at = format_date(modified_at_iso, "") # Assumes format_date_string is available

    date_clause = ""
    # Check if created_at is effectively epoch (e.g., year 1970)
    is_created_epoch = False
    if created_at_iso:
        try:
            # A simple check for epoch or very early dates
            created_dt_check = datetime.fromisoformat(created_at_iso.replace('Z', '+00:00'))
            if created_dt_check.year <= 1970:
                is_created_epoch = True
        except ValueError:
            pass # Parsing failed, treat as not epoch for this check

    if is_created_epoch and formatted_modified_at:
        date_clause = f"last updated on {formatted_modified_at}"
    elif formatted_created_at and formatted_modified_at and formatted_created_at != formatted_modified_at:
        date_clause = f"created on {formatted_created_at} and last modified on {formatted_modified_at}"
    elif formatted_modified_at:
        date_clause = f"as of {formatted_modified_at}"
    elif formatted_created_at: # Fallback if only created_at is valid and not epoch
        date_clause = f"created on {formatted_created_at}"

    if date_clause:
        description_parts.append(f"The status is '{status_type_friendly}', {date_clause}.")
    else:
        description_parts.append(f"The status is '{status_type_friendly}'.")


    # Title of the update
    title = status_data.get("title", "").strip()
    if title:
        description_parts.append(f"The title of this update is: \"{title}\".")

    # Text content of the update
    text_content = status_data.get("text", "").strip()
    if not text_content:
        html_text_content = status_data.get("html_text", "")
        if html_text_content: # Check if html_text is not None or empty before cleaning
             text_content = clean_html_notes(html_text_content) # Assumes clean_html_notes is available

    if text_content:
        description_parts.append(f"The details provided are: \"{text_content}\".")
    else:
        # If there's a title but no text content
        if title:
            description_parts.append("No further textual details were provided beyond the title.")
        # If there's no title and no text content
        else:
            description_parts.append("No specific title or textual details were provided with this status change.")

    return " ".join(description_parts)


def get_story_description(story_data):
    """
    Converts Asana Story JSON description into a human-readable text description.
    Assumes format_date_string and clean_html_notes functions are defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(story_data, dict):
        return "Invalid story description format."

    description_parts = []

    # Actor
    created_by_info = story_data.get("created_by")
    if created_by_info and created_by_info.get("name"):
        creator_name = created_by_info.get("name")
    else:
        # Default for system-generated stories without a specific user or if user info is incomplete
        creator_name = "System"  # Or "An automated process" / "Unknown user"

    # Timestamp - for stories, including time might be useful.
    # The format_date_string should ideally handle this or be adapted.
    # For this example, let's assume format_date_string gives a good date representation.
    # If format_date_string needs to be more specific for stories (e.g., include time),
    # it should be adjusted or a story-specific date formatter used.
    created_at_str = format_date(story_data.get("created_at"), "at an unspecified time")

    # Target of the story
    target_info = story_data.get("target", {})
    target_name = target_info.get("name", "an unspecified item")
    target_type = target_info.get("resource_type", "item")
    if target_info.get("resource_subtype"):  # e.g. "default_task" for a task
        target_subtype_description = target_info.get("resource_subtype").replace("_", " ")
        if target_subtype_description != target_type:  # Avoid "task task"
            target_type = f"{target_subtype_description}"  # More specific, like "default task"

    # Source of the story (web, email, api, etc.)
    source = story_data.get("source", "an unknown source")
    source_description = f"the {source} interface" if source != "unknown source" else source

    # Type of story (system event or comment)
    story_type = story_data.get("type", "event")  # Default to "event" if not specified
    story_subtype = story_data.get("resource_subtype", "")  # e.g., "duplicated", "comment_added"

    # Main text of the story
    # Prioritize html_text if available, then text, as html_text can be richer before cleaning.
    raw_event_text = story_data.get("html_text")
    if not raw_event_text:  # Fallback to 'text' if 'html_text' is empty or None
        raw_event_text = story_data.get("text", "")

    # Assuming clean_html_notes is robust enough to handle Asana's story HTML.
    # Asana's 'text' field is often already a good plain-text summary.
    # If html_text is just text + links, cleaning html_text is good.
    cleaned_event_text = clean_html_notes(raw_event_text).strip()

    # If cleaned_event_text is empty after cleaning, try to make a generic one from subtype
    if not cleaned_event_text and story_subtype:
        subtype_friendly = story_subtype.replace("_", " ").title()
        cleaned_event_text = f"A '{subtype_friendly}' action was performed."
    elif not cleaned_event_text:
        cleaned_event_text = "An unspecified update was recorded."

    # Sentence 1: Who, when, and regarding what
    # Using a slightly different phrasing based on whether the actor is a specific user or "System"
    if creator_name.lower() == "system":  # Actor is "System"
        description_parts.append(
            f"On {created_at_str}, a system event occurred concerning the {target_type} '{target_name}'.")
    else:  # Actor is a named user
        description_parts.append(
            f"On {created_at_str}, {creator_name} initiated an event related to the {target_type} '{target_name}'.")

    # Sentence 2: The details of the event/comment
    if story_type.lower() == "comment":
        # For comments, the cleaned_event_text is the comment itself.
        description_parts.append(f"The comment posted was: \"{cleaned_event_text}\".")
    else:  # For system events or other types
        # The cleaned_event_text often already mentions the actor for system events.
        description_parts.append(f"The recorded activity or system event stated: \"{cleaned_event_text}\".")

    # Sentence 3: Source of the event
    description_parts.append(f"This event originated from {source_description}.")

    return " ".join(description_parts)


def get_task_description(task_data):
    """
    Converts Asana Task JSON description into a human-readable text description.
    Assumes format_date_string, extract_names, and clean_html_notes
    functions are defined and available. GIDs are excluded.
    """
    if not isinstance(task_data, dict):
        return "Invalid task description format."

    description_parts = []

    task_name = task_data.get("name", "Unnamed Task")

    if task_data.get("is_rendered_as_separator"):
        description_parts.append(f"This is a separator item in a project, named '{task_name}'.")
        # For separators, less detail is usually needed.
        created_at_str = format_date(task_data.get("created_at"))
        modified_at_str = format_date(task_data.get("modified_at"))
        description_parts.append(f"It was created on {created_at_str} and last modified on {modified_at_str}.")

        memberships = task_data.get("memberships", [])
        if memberships:
            project_section_info = []
            for membership in memberships:
                proj_name = membership.get("project", {}).get("name", "an unnamed project")
                sec_name = membership.get("section", {}).get("name")
                if sec_name and sec_name.lower() != "untitled section":
                    project_section_info.append(f"the section '{sec_name}' of project '{proj_name}'")
                else:
                    project_section_info.append(f"project '{proj_name}'")
            if project_section_info:
                description_parts.append(f"It is located in {', '.join(project_section_info)}.")
        return " ".join(description_parts)

    # --- Regular Task Details ---
    description_parts.append(f"Task: '{task_name}'.")

    # Status and Completion
    if task_data.get("completed"):
        completed_at_str = format_date(task_data.get("completed_at"))
        description_parts.append(f"It is completed, marked as done on {completed_at_str}.")
    else:
        description_parts.append("It is currently an ongoing task.")

    # Assignee
    assignee_info = task_data.get("assignee")
    if assignee_info and assignee_info.get("name"):
        assignee_name = assignee_info.get("name")
        assignee_status = task_data.get("assignee_status", "").replace("_", " ")
        description_parts.append(f"It is assigned to {assignee_name} (status: {assignee_status}).")
    else:
        description_parts.append("It is currently unassigned.")

    # Dates (Due, Start, Created, Modified)
    due_date_str = format_date(task_data.get("due_on") or task_data.get("due_at"))
    if due_date_str != "not set":
        description_parts.append(f"The task is due on {due_date_str}.")

    start_date_str = format_date(task_data.get("start_on") or task_data.get("start_at"))
    if start_date_str != "not set":
        description_parts.append(f"It is scheduled to start on {start_date_str}.")

    created_at_str = format_date(task_data.get("created_at"))
    modified_at_str = format_date(task_data.get("modified_at"))

    creator_info = task_data.get("created_by", {})
    creator_name = creator_info.get(
        "name") if creator_info else None  # Asana's created_by for tasks might only have GID

    creation_clause = f"Created by {creator_name if creator_name else 'an unspecified user'} on {created_at_str}" if created_at_str != "not set" else ""
    modification_clause = f"last modified on {modified_at_str}" if modified_at_str != "not set" else ""

    if creation_clause and modification_clause:
        if created_at_str == modified_at_str and creator_name:  # If created and modified at same time by same person (or unspecified)
            description_parts.append(f"{creation_clause}.")
        else:
            description_parts.append(f"{creation_clause}, and {modification_clause}.")
    elif creation_clause:
        description_parts.append(f"{creation_clause}.")
    elif modification_clause:  # Should not happen if created_at is always present
        description_parts.append(f"It was {modification_clause}.")

    # Parent Task (Subtask Info)
    parent_info = task_data.get("parent")
    if parent_info and parent_info.get("name"):
        parent_name = parent_info.get("name")
        description_parts.append(f"This is a subtask of '{parent_name}'.")

    # Notes / Description
    notes_text = task_data.get("notes", "").strip()
    html_notes_cleaned = clean_html_notes(task_data.get("html_notes", ""))

    task_description = ""
    if html_notes_cleaned:  # Prefer cleaned HTML notes
        task_description = html_notes_cleaned
    elif notes_text:
        task_description = notes_text

    if task_description:
        description_parts.append(f"Description/Notes: {task_description}")
    else:
        description_parts.append("No specific notes or description are provided for this task.")

    # Project Memberships
    memberships = task_data.get("memberships", [])
    if memberships:
        project_section_info = []
        for membership in memberships:
            proj_name = membership.get("project", {}).get("name", "an unnamed project")
            sec_name = membership.get("section", {}).get("name")
            if sec_name and sec_name.lower() != "untitled section":  # Avoid "Untitled section" unless it's the only info
                project_section_info.append(f"the section '{sec_name}' of project '{proj_name}'")
            else:
                project_section_info.append(f"project '{proj_name}'")
        if project_section_info:
            description_parts.append(f"It belongs to {', '.join(project_section_info)}.")

    # Followers
    followers_names = extract_names(task_data.get("followers"), default_if_empty="")
    if followers_names:
        description_parts.append(f"Followers include: {followers_names}.")

    # Tags
    tags_list = task_data.get("tags", [])
    if tags_list:
        tag_names = [tag.get("name") for tag in tags_list if tag.get("name")]
        if tag_names:
            description_parts.append(f"Tagged with: {', '.join(tag_names)}.")

    # Custom Fields
    custom_fields_data = task_data.get("custom_fields", [])
    if custom_fields_data:
        cf_strings = []
        for cf in custom_fields_data:
            cf_name = cf.get("name")
            # display_value is generally reliable for a string representation.
            cf_display_value = cf.get("display_value")
            # Alternative way to get value if display_value is not preferred or for specific types:
            # cf_type = cf.get("resource_subtype")
            # cf_value_str = ""
            # if cf_type == "enum" and cf.get("enum_value"):
            #     cf_value_str = cf.get("enum_value", {}).get("name", cf_display_value)
            # elif cf_type == "multi_enum" and cf.get("multi_enum_values"):
            #     option_names = [opt.get("name") for opt in cf.get("multi_enum_values", []) if opt.get("name")]
            #     cf_value_str = ", ".join(option_names) if option_names else cf_display_value
            # elif cf_type == "number":
            #     cf_value_str = str(cf.get("number_value", cf_display_value))
            # elif cf_type == "text":
            #     cf_value_str = cf.get("text_value", cf_display_value)
            # else: #people, date etc. display_value is usually best
            #     cf_value_str = cf_display_value

            if cf_name and cf_display_value is not None:  # Ensure value is not None before adding
                cf_strings.append(f"'{cf_name}': {cf_display_value}")
        if cf_strings:
            description_parts.append(f"Custom field values: {'; '.join(cf_strings)}.")

    # Subtasks count
    num_subtasks = task_data.get("num_subtasks", 0)
    if num_subtasks > 0:
        description_parts.append(f"It has {num_subtasks} subtask{'s' if num_subtasks > 1 else ''}.")

    # Actual Time
    actual_time_minutes = task_data.get("actual_time_minutes")
    if actual_time_minutes is not None and actual_time_minutes > 0:
        hours = actual_time_minutes // 60
        minutes = actual_time_minutes % 60
        time_str = ""
        if hours > 0:
            time_str += f"{hours} hour{'s' if hours > 1 else ''}"
        if minutes > 0:
            if time_str: time_str += " and "
            time_str += f"{minutes} minute{'s' if minutes > 1 else ''}"
        description_parts.append(f"Actual time logged: {time_str}.")

    # Dependencies and Dependents
    dependencies = task_data.get("dependencies", [])
    if dependencies:
        dep_names = extract_names(dependencies, default_if_empty="")
        if dep_names:
            description_parts.append(f"This task is blocked by: {dep_names}.")

    dependents = task_data.get("dependents", [])
    if dependents:
        dep_names = extract_names(dependents, default_if_empty="")
        if dep_names:
            description_parts.append(f"This task is blocking: {dep_names}.")

    # Workspace
    workspace_name = task_data.get("workspace", {}).get("name")
    if workspace_name:
        description_parts.append(f"It resides in the '{workspace_name}' workspace.")

    # Permalink
    permalink = task_data.get("permalink_url")
    if permalink:
        description_parts.append(f"The direct link to this task is: {permalink}.")

    # Likes/Hearts (usually less important for KB, but can be included)
    # num_likes = task_data.get("num_likes", 0)
    # num_hearts = task_data.get("num_hearts", 0)
    # if num_likes > 0:
    #     description_parts.append(f"It has {num_likes} like{'s' if num_likes > 1 else ''}.")
    # if num_hearts > 0:
    #     description_parts.append(f"It has {num_hearts} heart{'s' if num_hearts > 1 else ''}.")

    return " ".join(description_parts)

def get_team_description(team_data):
    """
    Converts Asana Team JSON description into a human-readable text description.
    Assumes the clean_html_notes function is defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(team_data, dict):
        return "Invalid team description format."

    description_parts = []

    team_name = team_data.get("name", "Unnamed Team")
    description_parts.append(f"This is an Asana team named '{team_name}'.")

    # Organization (Workspace)
    organization_info = team_data.get("organization")
    if organization_info and organization_info.get("name"):
        org_name = organization_info.get("name")
        description_parts.append(f"It belongs to the '{org_name}' workspace.")
    else:
        description_parts.append("The workspace this team belongs to is not specified.")

    # Description
    team_description_text = team_data.get("description", "").strip()
    if not team_description_text:
        # Fallback to cleaned HTML description if plain description is empty
        html_desc = team_data.get("html_description", "")
        # Assuming clean_html_notes function is available
        team_description_text = clean_html_notes(html_desc)

    if team_description_text:
        description_parts.append(f"The team's description is: \"{team_description_text}\".")
    else:
        description_parts.append("No specific description is provided for this team.")

    # Permalink URL
    permalink_url = team_data.get("permalink_url")
    if permalink_url:
        description_parts.append(f"More details about this team can be found at its Asana page: {permalink_url}.")

    # Potential future additions if the API provides them and they are relevant:
    # - Number of members (if available directly without fetching members separately)
    # - Team visibility (public to org, private, etc. - if this field exists for teams)

    return " ".join(description_parts)


def get_team_membership_description(membership_data):
    """
    Converts Asana Team Membership JSON description into a human-readable text description.
    GIDs are excluded from the output.
    """
    if not isinstance(membership_data, dict):
        return "Invalid team membership description format."

    description_parts = []

    user_info = membership_data.get("user", {})
    user_name = user_info.get("name", "An unnamed user")

    team_info = membership_data.get("team", {})
    team_name = team_info.get("name", "an unnamed team")

    description_parts.append(f"{user_name} is associated with the team '{team_name}'.")

    is_admin = membership_data.get("is_admin", False)
    is_guest = membership_data.get("is_guest", False)
    is_limited_access = membership_data.get("is_limited_access", False)

    role_description_clauses = []

    if is_admin:
        role_description_clauses.append("they are an administrator")

    if is_guest:
        if is_admin:  # If already an admin, phrase it as "also a guest"
            if role_description_clauses:  # Check if "they are an administrator" is already there
                role_description_clauses[-1] += " and also a guest member"
            else:  # Should not happen if is_admin was true and added to list
                role_description_clauses.append("they are a guest member")
        else:  # Not an admin, just a guest
            role_description_clauses.append("they are a guest member")

    if is_limited_access:
        if role_description_clauses:  # If there's already a description (admin and/or guest)
            # Append "and have limited access" to the existing description
            role_description_clauses[-1] += " and have limited access privileges"
        else:  # Only limited_access is true
            role_description_clauses.append("they have limited access privileges")

    if not role_description_clauses:  # All flags (is_admin, is_guest, is_limited_access) were false
        description_parts.append("They are a standard member with full access in this team.")
    else:
        # At this point, role_description_clauses should contain a single string
        # representing the combined role description.
        # e.g., ["they are an administrator and also a guest member and have limited access privileges"]
        # Capitalize the first letter of the description.
        full_role_sentence = role_description_clauses[0].capitalize() + "."
        description_parts.append(full_role_sentence)

    return " ".join(description_parts)

def get_user_description(user_data):
    """
    Converts Asana User JSON description into a human-readable text description.
    GIDs are excluded from the output.
    """
    if not isinstance(user_data, dict):
        return "Invalid user description format."

    description_parts = []

    user_name = user_data.get("name", "An unnamed user")
    user_email = user_data.get("email")

    description_parts.append(f"This is an Asana user named '{user_name}'.")

    if user_email:
        description_parts.append(f"Their registered email address is {user_email}.")
    else:
        description_parts.append("Their email address is not specified.")

    # Photo
    if user_data.get("photo"): # Check if the photo object exists and is not null
        description_parts.append("They have a profile picture set up in Asana.")
    else:
        description_parts.append("They do not have a profile picture set up in Asana.")

    # Workspaces
    workspaces_list = user_data.get("workspaces", [])
    if workspaces_list:
        workspace_names = [ws.get("name") for ws in workspaces_list if ws.get("name")]
        if workspace_names:
            if len(workspace_names) == 1:
                description_parts.append(f"They are a member of the '{workspace_names[0]}' workspace.")
            else:
                # Using a simple join for multiple workspaces
                workspaces_str = ", ".join([f"'{name}'" for name in workspace_names[:-1]])
                if len(workspace_names) > 1:
                    workspaces_str += f"{' and ' if len(workspace_names) > 2 else ' and '}'{workspace_names[-1]}'"
                else: # Should not happen if len > 1, but good for safety
                     workspaces_str = f"'{workspace_names[0]}'"
                description_parts.append(f"They are a member of the following workspaces: {workspaces_str}.")
        else:
            description_parts.append("Their workspace memberships are not clearly specified.")
    else:
        description_parts.append("They are not explicitly associated with any workspaces in this description.")

    # Placeholder for other user-specific information if available and relevant from API:
    # e.g., user's role within a workspace (if provided directly on user object),
    # date joined, last activity (though these are usually not on the basic user object).

    return " ".join(description_parts)

from datetime import datetime

# Assume the format_date function from previous examples is available in the same scope.
# If not, it would need to be defined here or passed as an argument.
# For example, a suitable version would be:
# def format_date(date_str):
#     """Helper function to format ISO date strings (datetime or date-only) nicely."""
#     if not date_str:
#         return "not specified"
#     try: # Try parsing as datetime first
#         if '.' in date_str and 'T' in date_str and 'Z' in date_str:
#             dt_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
#             return dt_obj.strftime("%B %d, %Y at %I:%M %p UTC") # Include time for datetimes
#         elif 'T' in date_str and 'Z' in date_str: # Datetime without milliseconds
#             dt_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ")
#             return dt_obj.strftime("%B %d, %Y at %I:%M %p UTC") # Include time
#         else: # Try parsing as date-only
#             dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
#             return dt_obj.strftime("%B %d, %Y")
#     except ValueError:
#         return date_str # Return original if all parsing attempts fail

def get_tag_description(tag_data):
    """
    Converts Asana Tag JSON description into a human-readable text description.
    Assumes format_date_string and extract_names functions are defined and available.
    GIDs are excluded from the output.
    """
    if not isinstance(tag_data, dict):
        return "Invalid tag description format."

    description_parts = []

    tag_name = tag_data.get("name", "Unnamed Tag")
    description_parts.append(f"This is an Asana tag named '{tag_name}'.")

    # Color
    tag_color = tag_data.get("color") # Can be null or "none"
    if tag_color and tag_color.lower() != "none":
        description_parts.append(f"It is visually represented with a '{tag_color}' color.")
    else:
        description_parts.append("It does not have a specific color assigned.")

    # Creation Date
    created_at_str = format_date(tag_data.get("created_at"), "an unknown date") # Assumes format_date_string
    description_parts.append(f"The tag was created on {created_at_str}.")

    # Workspace
    workspace_info = tag_data.get("workspace", {})
    workspace_name = workspace_info.get("name")
    if workspace_name:
        description_parts.append(f"It belongs to the '{workspace_name}' workspace.")
    else:
        description_parts.append("The workspace this tag belongs to is not specified.")

    # Notes
    tag_notes = tag_data.get("notes", "").strip()
    if tag_notes:
        description_parts.append(f"Additional notes for this tag: \"{tag_notes}\".")
    else:
        description_parts.append("There are no specific notes associated with this tag.")

    # Followers (though typically empty for tags in many setups, good to include if present)
    followers_list = tag_data.get("followers", [])
    followers_names = extract_names(followers_list, default_if_empty="") # Assumes extract_names
    if followers_names:
        description_parts.append(f"It is being followed by: {followers_names}.")
    # else:
        # description_parts.append("This tag currently has no followers listed.") # Optional to state no followers

    # Permalink URL
    permalink_url = tag_data.get("permalink_url")
    if permalink_url:
        description_parts.append(f"More details about this tag can be found at its Asana page: {permalink_url}.")

    return " ".join(description_parts)

func_dict = {
    'team': get_team_description,
    'user': get_user_description,
    'team_membership': get_team_membership_description,
    'project': get_project_description,
    'custom_field': get_custom_field_description,
    'project_template': get_project_template_description,
    'task': get_task_description,
    'section': get_section_description,
    'tag': get_tag_description,
    'status_update': get_status_update_description,
    'story': get_story_description,
    'attachment': get_attachment_description,
}

def create_openai_batch_embedding_jsonl(
        data: dict,
        output_filepath: str,
        resourse_type: str,
        model_name: str = "text-embedding-ada-002",
) -> None:
    """
    Creates a JSONL file for OpenAI batch embedding requests.

    Args:
        texts_array (list[str]): A list of text strings to be embedded.
        output_filepath (str): The path where the JSONL file will be saved.
        model_name (str, optional): The OpenAI embedding model to use.
                                    Defaults to "text-embedding-ada-002".
                                    Other options: "text-embedding-3-small", "text-embedding-3-large".
        custom_id_prefix (str, optional): A prefix for generating custom IDs.
                                          Defaults to "request".
    """
    # Optional: Create parent directory if it doesn't exist
    output_dir = os.path.dirname(output_filepath)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created directory: {output_dir}")

    with open(output_filepath, 'w', encoding='utf-8') as f:
        for k in data:
            # Create the JSON object for this request
            json_request = {
                "custom_id": data[k]['gid'],  # Ensures unique ID, e.g., request-1, request-2
                "method": "POST",
                "url": "/v1/embeddings",  # The API endpoint for embeddings
                "body": {
                    "input": func_dict[resourse_type](data[k]),
                    "model": model_name
                }
            }
            # Write the JSON object as a string on a new line
            f.write(json.dumps(json_request) + "\n")

    print(f"Successfully created JSONL file at: {output_filepath}")
    print(f"Total requests written: {len(data)}")


if __name__ == '__main__':
    space = load()
    # print(get_project_description(list(space['project'].values())[0]))
    # print(get_attachment_description(list(space['attachment'].values())[0]))
    # print(get_custom_field_description(list(space['custom_field'].values())[0]))
    # print(get_project_template_description(list(space['project_template'].values())[0]))
    # print(get_section_description(list(space['section'].values())[0]))
    # print(get_status_update_description(list(space['status_update'].values())[0]))
    # print(get_story_description(list(space['story'].values())[1231]))
    # print(get_tag_description(list(space['tag'].values())[100]))
    # print(get_task_description(list(space['task'].values())[1231]))
    # print(get_team_description(list(space['team'].values())[1]))
    # print(get_team_membership_description(list(space['team_membership'].values())[1]))
    # print(get_user_description(list(space['user'].values())[1]))

    # model = 'text-embedding-3-small'
    # for key in space:
    #     if key == "workspace":
    #         continue
    #     create_openai_batch_embedding_jsonl(
    #         data=space[key],
    #         output_filepath=f"MVP_data/asana/description/{key}.jsonl",
    #         resourse_type=key,
    #         model_name=model,
    #     )

    # files = {}
    # files_id = {}
    # for key in space:
    #     if key == "workspace":
    #         continue
    #     batch_input_file = openAI.files.create(
    #         file=open(f"description/{key}.jsonl", "rb"),
    #         purpose="batch"
    #     )
    #     files[key] = batch_input_file
    #     files_id[key] = batch_input_file.id
    #
    #     print(batch_input_file)
    # json.dump(files, open("files.json", "w"), indent=4)
    # json.dump(files_id, open("files_id.json", "w"), indent=4)

    # files = {}
    # for key in space:
    #     if key == "workspace":
    #         continue
    #     openAI.batches.create(
    #         input_file_id=files[key]["id"],
    #         endpoint="/v1/chat/completions",
    #         completion_window="24h",
    #         metadata={
    #             "description": "nightly eval job"
    #         }
    #     )



