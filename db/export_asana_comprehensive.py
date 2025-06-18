"""
Comprehensive Asana Data Export and Upsert Script
Exports all Asana data from a specific workspace and upserts to MongoDB and Pinecone.
"""

import json
import os
import time
import threading
import copy
import datetime
import re
import html
import sys
import certifi
import logging
from datetime import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import traceback
import os

# External dependencies
import asana
from asana.rest import ApiException
from pinecone import Pinecone, ServerlessSpec
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from openai import OpenAI
from requests import request
from tqdm import tqdm
from config import pinecone_info, mongo_info

# Configuration and Constants
ASANA_ACCESS_TOKEN = os.environ.get("ASANA_ACCESS_TOKEN")
WORKSPACE_ID = "1120263180104321"
INDEX_NAME = pinecone_info["index"]
ENV = pinecone_info["env"]  # Changed to "data" as per requirements
DB_NAME = mongo_info["database"]
COLLECTION_NAME = mongo_info["collection"]  # Changed to "data" as per requirements

# Global variables for threading
lock = Lock()
progress_lock = Lock()
log_lock = Lock()
error_lock = Lock()

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    # Clear log files
    with open('log.txt', 'w') as f:
        f.write(f"=== Asana Export Started at {datetime.datetime.now()} ===\n")
    with open('error.txt', 'w') as f:
        f.write(f"=== Error Log Started at {datetime.datetime.now()} ===\n")

def log_info(message):
    """Thread-safe logging to log.txt"""
    with log_lock:
        with open('log.txt', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now()}: {message}\n")
        print(f"INFO: {message}")

def log_error(message, error=None):
    """Thread-safe error logging to error.txt"""
    with error_lock:
        with open('error.txt', 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now()}: {message}\n")
            if error:
                f.write(f"Error details: {str(error)}\n")
                f.write(f"Traceback: {traceback.format_exc()}\n===========================================================\n")
        print(f"ERROR: {message}, {str(error)}")

# Setup Asana client
configuration = asana.Configuration()
configuration.access_token = ASANA_ACCESS_TOKEN
api_client = asana.ApiClient(configuration)

# OpenAI client
ai_client = OpenAI()

# Resource types to ignore during processing
IGNORE_TYPES = ['custom_field_setting', 'enum_option']

# Client-related resource types
CLIENT_RELATED_TYPES = ["project", "task", "section", "story"]

# API field configurations
OPT_FIELDS = {
    'simple': {'opt_fields': 'gid,resource_type'},
    'team': {'opt_fields': 'description,html_description'},
    'project': {'opt_fields': 'created_from_template,project_brief,html_notes'},
    'custom_field': {'opt_fields': 'description'},
    'task': {'opt_fields': 'created_by,dependencies,dependents,html_notes,is_rendered_as_separator,num_subtasks,description'},
    'status_update': {'opt_fields': 'html_text'},
    'story': {'opt_fields': 'html_text'}
}

# API instances
API_INSTANCES = {
    'workspace': asana.WorkspacesApi(api_client),
    'team': asana.TeamsApi(api_client),
    'user': asana.UsersApi(api_client),
    'team_membership': asana.TeamMembershipsApi(api_client),
    'project': asana.ProjectsApi(api_client),
    'custom_field': asana.CustomFieldsApi(api_client),
    'project_template': asana.ProjectTemplatesApi(api_client),
    'task': asana.TasksApi(api_client),
    'section': asana.SectionsApi(api_client),
    'tag': asana.TagsApi(api_client),
    'status_update': asana.StatusUpdatesApi(api_client),
    'story': asana.StoriesApi(api_client),
    'attachment': asana.AttachmentsApi(api_client),
    'event': asana.EventsApi(api_client),
}

# API get method mappings
API_GET_METHODS = {
    'workspace': API_INSTANCES['workspace'].get_workspace,
    'team': API_INSTANCES['team'].get_team,
    'user': API_INSTANCES['user'].get_user,
    'team_membership': API_INSTANCES['team_membership'].get_team_membership,
    'project': API_INSTANCES['project'].get_project,
    'custom_field': API_INSTANCES['custom_field'].get_custom_field,
    'project_template': API_INSTANCES['project_template'].get_project_template,
    'task': API_INSTANCES['task'].get_task,
    'section': API_INSTANCES['section'].get_section,
    'tag': API_INSTANCES['tag'].get_tag,
    'status_update': API_INSTANCES['status_update'].get_status,
    'story': API_INSTANCES['story'].get_story,
    'attachment': API_INSTANCES['attachment'].get_attachment,
}

# # API delete method mappings
# API_DELETE_METHODS = {
#     'project': API_INSTANCES['project'].delete_project,
#     'task': API_INSTANCES['task'].delete_task,
#     'section': API_INSTANCES['section'].delete_section,
#     'tag': API_INSTANCES['tag'].delete_tag,
#     'story': API_INSTANCES['story'].delete_story
# }

# Template Functions for Converting Asana Data to Human-Readable Descriptions
def format_date(date_str, default="not set"):
    """Helper function to format ISO date strings or return a default."""
    if not date_str:
        return default
    try:
        dt_obj = dt.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt_obj.strftime("%B %d, %Y")
    except ValueError:
        return default

def clean_html_notes(html_notes_str):
    """Basic HTML cleaner for Asana notes."""
    if not html_notes_str:
        return ""
    # Remove body tags
    text = re.sub(r'<body[^>]*>(.*?)</body>', r'\1', html_notes_str, flags=re.IGNORECASE | re.DOTALL)
    # Remove other common HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Replace common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

def get_project_description(project_data):
    """Converts Asana project JSON to human-readable description."""
    if not isinstance(project_data, dict):
        return "Invalid project description format."

    name = project_data.get("name", "Unnamed Project")
    description_parts = [f"Project Name: {name}."]

    status = "archived" if project_data.get("archived") else "active"
    completion = "completed" if project_data.get("completed") else "ongoing"
    description_parts.append(f"It is currently {status} and {completion}.")

    if project_data.get("completed") and project_data.get("completed_at"):
        description_parts.append(f"It was completed on {format_date(project_data.get('completed_at'))}.")

    # Owner information
    try:
        owner_name = project_data.get("owner", {})
        if owner_name is None:
            owner_name = 'N/A'
        else:
            owner_name = owner_name.get("name", "N/A")
        if owner_name != "N/A":
            description_parts.append(f"The project is owned by {owner_name}.")
    except AttributeError:
        pass

    # Team and workspace
    team_name = project_data.get("team", {}).get("name", "N/A")
    if team_name != "N/A":
        description_parts.append(f"It belongs to the '{team_name}' team.")

    workspace_name = project_data.get("workspace", {}).get("name", "N/A")
    if workspace_name != "N/A":
        description_parts.append(f"It is part of the '{workspace_name}' workspace.")

    # Dates
    created_at = format_date(project_data.get("created_at"))
    modified_at = format_date(project_data.get("modified_at"))
    description_parts.append(f"Created on {created_at}, last modified on {modified_at}.")

    # Notes
    notes = project_data.get("notes", "").strip()
    html_notes_cleaned = clean_html_notes(project_data.get("html_notes", ""))

    project_description = notes or html_notes_cleaned
    if project_description:
        description_parts.append(f"Project Description/Notes: {project_description}")
    else:
        description_parts.append("There are no specific notes or description provided for this project.")

    return " ".join(description_parts)

def get_task_description(task_data):
    """Converts Asana Task JSON to human-readable description."""
    if not isinstance(task_data, dict):
        return "Invalid task description format."

    description_parts = []
    task_name = task_data.get("name", "Unnamed Task")

    if task_data.get("is_rendered_as_separator"):
        description_parts.append(f"This is a separator item in a project, named '{task_name}'.")
        created_at_str = format_date(task_data.get("created_at"))
        modified_at_str = format_date(task_data.get("modified_at"))
        description_parts.append(f"It was created on {created_at_str} and last modified on {modified_at_str}.")
        return " ".join(description_parts)

    description_parts.append(f"Task: '{task_name}'.")

    # Status and completion
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

    # Notes/Description
    notes_text = task_data.get("notes", "").strip()
    html_notes_cleaned = clean_html_notes(task_data.get("html_notes", ""))
    task_description = html_notes_cleaned or notes_text

    if task_description:
        description_parts.append(f"Description/Notes: {task_description}")
    else:
        description_parts.append("No specific notes or description are provided for this task.")

    return " ".join(description_parts)

def get_story_description(story_data):
    """Converts Asana Story JSON to human-readable description."""
    if not isinstance(story_data, dict):
        return "Invalid story description format."

    description_parts = []

    # Actor
    created_by_info = story_data.get("created_by")
    if created_by_info and created_by_info.get("name"):
        creator_name = created_by_info.get("name")
    else:
        creator_name = "System"

    # Timestamp
    created_at_str = format_date(story_data.get("created_at"), "at an unspecified time")

    # Target
    target_info = story_data.get("target", {})
    target_name = target_info.get("name", "an unspecified item")
    target_type = target_info.get("resource_type", "item")

    # Main text
    raw_event_text = story_data.get("html_text") or story_data.get("text", "")
    cleaned_event_text = clean_html_notes(raw_event_text).strip()

    if not cleaned_event_text:
        story_subtype = story_data.get("resource_subtype", "")
        if story_subtype:
            subtype_friendly = story_subtype.replace("_", " ").title()
            cleaned_event_text = f"A '{subtype_friendly}' action was performed."
        else:
            cleaned_event_text = "An unspecified update was recorded."

    # Construct description
    if creator_name.lower() == "system":
        description_parts.append(f"On {created_at_str}, a system event occurred concerning the {target_type} '{target_name}'.")
    else:
        description_parts.append(f"On {created_at_str}, {creator_name} initiated an event related to the {target_type} '{target_name}'.")

    story_type = story_data.get("type", "event")
    if story_type.lower() == "comment":
        description_parts.append(f"The comment posted was: \"{cleaned_event_text}\".")
    else:
        description_parts.append(f"The recorded activity or system event stated: \"{cleaned_event_text}\".")

    return " ".join(description_parts)

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

def get_attachment_description(attachment_data):
    """
    Converts Asana attachment JSON description into a human-readable text description.
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

    # Formula field
    is_formula = custom_field_data.get("is_formula_field", False)
    if is_formula:
        description_parts.append("This field's value is calculated based on a formula.")

    # Global vs. Local Scope
    is_global = custom_field_data.get("is_global_to_workspace", False)
    scope_description = "available across the entire workspace" if is_global else "configured for specific projects or portfolios"

    # Privacy Setting
    privacy = custom_field_data.get("privacy_setting", "unknown")
    privacy_friendly = privacy.replace("_", " ")  # e.g., "public with guests"

    description_parts.append(f"The field is {scope_description}, and its privacy is set to '{privacy_friendly}'.")

    return " ".join(description_parts)

def get_project_template_description(template_data):
    """
    Converts Asana Project Template JSON description into a human-readable text description.
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
    """
    if not isinstance(section_data, dict):
        return "Invalid section description format."

    description_parts = []

    section_name = section_data.get("name", "Unnamed Section")
    created_at_str = format_date(section_data.get("created_at"), "an unknown date")

    project_info = section_data.get("project", {})
    project_name = project_info.get("name", "an unspecified project")

    # Sentence 1: Basic information about the section
    description_parts.append(f"This is a section named '{section_name}'.")

    # Sentence 2: Context within a project
    description_parts.append(f"It is part of the project '{project_name}'.")

    # Sentence 3: Creation date
    description_parts.append(f"The section was created on {created_at_str}.")

    return " ".join(description_parts)

def get_status_update_description(status_data):
    """
    Converts Asana Status Update JSON description into a human-readable text description.
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

    formatted_created_at = format_date(created_at_iso, "") 
    formatted_modified_at = format_date(modified_at_iso, "") 

    date_clause = ""
    # Check if created_at is effectively epoch (e.g., year 1970)
    is_created_epoch = False
    if created_at_iso:
        try:
            # A simple check for epoch or very early dates
            created_dt_check = dt.fromisoformat(created_at_iso.replace('Z', '+00:00'))
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
             text_content = clean_html_notes(html_text_content)

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

def get_team_description(team_data):
    """
    Converts Asana Team JSON description into a human-readable text description.
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
        team_description_text = clean_html_notes(html_desc)

    if team_description_text:
        description_parts.append(f"The team's description is: \"{team_description_text}\".")
    else:
        description_parts.append("No specific description is provided for this team.")

    # Permalink URL
    permalink_url = team_data.get("permalink_url")
    if permalink_url:
        description_parts.append(f"More details about this team can be found at its Asana page: {permalink_url}.")

    return " ".join(description_parts)

def get_team_membership_description(membership_data):
    """
    Converts Asana Team Membership JSON description into a human-readable text description.
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
        full_role_sentence = role_description_clauses[0].capitalize() + "."
        description_parts.append(full_role_sentence)

    return " ".join(description_parts)

def get_user_description(user_data):
    """
    Converts Asana User JSON description into a human-readable text description.
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

    return " ".join(description_parts)

def get_tag_description(tag_data):
    """
    Converts Asana Tag JSON description into a human-readable text description.
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
    created_at_str = format_date(tag_data.get("created_at"), "an unknown date")
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
    followers_names = extract_names(followers_list, default_if_empty="")
    if followers_names:
        description_parts.append(f"It is being followed by: {followers_names}.")

    # Permalink URL
    permalink_url = tag_data.get("permalink_url")
    if permalink_url:
        description_parts.append(f"More details about this tag can be found at its Asana page: {permalink_url}.")

    return " ".join(description_parts)

# Template function mapping
TEMPLATE_FUNCTIONS = {
    'project': get_project_description,
    'task': get_task_description,
    'story': get_story_description,
    'team': get_team_description,
    'user': get_user_description,
    'team_membership': get_team_membership_description,
    'custom_field': get_custom_field_description,
    'project_template': get_project_template_description,
    'section': get_section_description,
    'tag': get_tag_description,
    'status_update': get_status_update_description,
    'attachment': get_attachment_description,
}

# Utility Functions
def get_response(func, *args, **kwargs):
    """Make API requests with retry logic for rate limiting."""
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            if e.status == 429:
                wait_time = min(60, 10 * (2 ** retry_count))  # Exponential backoff
                log_error(f"Rate limit hit. Waiting {wait_time} seconds before retry {retry_count + 1}/{max_retries}")
                time.sleep(wait_time)
                retry_count += 1
            else:
                log_error(f"API Exception: {e.status} - {e}", e)
                raise e
        except Exception as e:
            log_error(f"Unexpected error in API call: {str(e)}", e)
            if retry_count < max_retries - 1:
                time.sleep(10)
                retry_count += 1
            else:
                raise e
    
    raise Exception(f"Max retries ({max_retries}) exceeded for API call")

def get_data_fetcher(resource_type, additional_fields=False):
    """Create a data fetcher function for a specific resource type."""
    def fetch(gid):
        try:
            data = get_response(API_GET_METHODS[resource_type], gid, opts={})
            if additional_fields and resource_type in OPT_FIELDS:
                additional_data = get_response(API_GET_METHODS[resource_type], gid, opts=OPT_FIELDS[resource_type])
                data.update(additional_data)
            return data
        except Exception as e:
            log_error(f"Failed to fetch {resource_type} with gid {gid}", e)
            return None
    return fetch

# Data fetchers for each resource type
DATA_FETCHERS = {
    'workspace': get_data_fetcher('workspace'),
    'team': get_data_fetcher('team', True),
    'user': get_data_fetcher('user'),
    'team_membership': get_data_fetcher('team_membership'),
    'project': get_data_fetcher('project', True),
    'custom_field': get_data_fetcher('custom_field', True),
    'project_template': get_data_fetcher('project_template'),
    'task': get_data_fetcher('task', True),
    'section': get_data_fetcher('section'),
    'tag': get_data_fetcher('tag'),
    'status_update': get_data_fetcher('status_update', True),
    'story': get_data_fetcher('story', True),
    'attachment': get_data_fetcher('attachment'),
}

def extract_client_id(project_name):
    """Extract client ID from project name (first 3 digits)."""
    if not project_name:
        return []
    
    match = re.match(r'^(\d{3})', project_name.strip())
    if match:
        return [match.group(1)]
    return []

def convert_datetime_fields(data):
    """Convert date string fields to datetime objects for MongoDB."""
    if not isinstance(data, dict):
        return data
    
    date_fields = ["created_at", "completed_at", "due_on", "due_date", "modified_at"]
    
    for field in date_fields:
        if field in data and data[field] is not None:
            try:
                if isinstance(data[field], str):
                    data[field] = dt.fromisoformat(data[field].replace('Z', '+00:00'))
            except (ValueError, TypeError) as e:
                log_error(f"Failed to convert datetime field {field}: {data[field]}", e)
    
    return data

def add_metadata_fields(data, parent_clients=None):
    """Add required metadata fields to data."""
    if not isinstance(data, dict):
        return data
    
    # Add "from" field
    data["from"] = "Asana"
    
    # Add "type" field
    resource_type = data.get("resource_type", "")
    if resource_type in CLIENT_RELATED_TYPES:
        data["type"] = "client_spec"
    else:
        data["type"] = "general"
    
    # Add "client" field
    if resource_type == "project":
        project_name = data.get("name", "")
        data["client"] = extract_client_id(project_name)
    elif resource_type in ["task", "section", "story"] and parent_clients:
        data["client"] = parent_clients
    else:
        data["client"] = []
    
    return data

def expand_data(data, space, parent_clients=None, index_model=None, collection=None, first=False):
    """Recursively expand Asana data and fetch related resources."""
    if not isinstance(data, dict):
        return
        
    if 'gid' in data and 'resource_type' in data and data['resource_type'] not in IGNORE_TYPES:
        resource_type = data['resource_type']
        gid = data['gid']

        if resource_type == 'attachment':
            return
        
        if resource_type not in space:
            space[resource_type] = {}

        resource = collection.find_one({"gid": gid})
        if not resource or first:
            try:
                full_data = DATA_FETCHERS[resource_type](gid)
                if full_data:
                    # Add metadata fields
                    full_data = add_metadata_fields(full_data, parent_clients)
                    
                    # Upsert to databases automatically
                    # if index_model is not None and collection is not None:
                    if resource_type == 'project':
                        sync = ''
                        try:
                            if resource:
                                webhook_info = resource.get('webhook_info')
                            else:
                                webhook_info = request("get", f"https://whitemarketing.onrender.com/establish-webhook/{gid}").json().get('webhook_info')
                            full_data.update({'webhook_info': webhook_info})
                            api_response = asana.EventsApi(api_client).get_events(gid, {}, full_payload=True)
                        except ApiException as e:
                            sync = json.loads(e.body)["sync"]
                            full_data['sync'] = sync
                        log_info(f"\n{json.dumps(full_data, indent=4)}")
                    sync_upsert_data(full_data, index_model, collection, resource_type)

                    with lock:
                        space[resource_type][gid] = full_data
                        if resource_type not in space.get('updated', []):
                            space.setdefault('updated', []).append(resource_type)
                    
                    # Recursively process nested data
                    for key in full_data:
                        if isinstance(full_data[key], dict):
                            expand_data(full_data[key], space, parent_clients, index_model, collection)
                        elif isinstance(full_data[key], list):
                            for el in full_data[key]:
                                if isinstance(el, dict):
                                    expand_data(el, space, parent_clients, index_model, collection)
            except Exception as e:
                log_error(f"Failed to expand data for {resource_type} {gid}", e)
        else:
            return

def setup_databases():
    """Setup Pinecone and MongoDB connections."""
    index_model = None
    collection = None
    
    # Setup Pinecone
    try:
        pc = Pinecone(api_key='pcsk_6QLqUr_7neqLCLusw49wn3FRNKoWgsN15C3aTxj5sCLL13VQJLYCg4fBdfUCAPfFPe6P1m')
        
        if not pc.has_index(INDEX_NAME):
            index_model = pc.create_index(
                name=INDEX_NAME,
                vector_type="dense",
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                deletion_protection="disabled",
                tags={"environment": ENV}
            )
            log_info("Created new Pinecone index")
        else:
            index_model = pc.Index(INDEX_NAME)
            log_info("Connected to existing Pinecone index")
    except Exception as e:
        log_error("Failed to setup Pinecone", e)
    
    # Setup MongoDB
    try:
        mongo_client = MongoClient(
            mongo_info["url"],
            tlsCAFile=certifi.where()
        )
        mongo_client.admin.command('ismaster')
        collection = mongo_client[DB_NAME][COLLECTION_NAME]
        log_info("Connected to MongoDB successfully")
    except ConnectionFailure as e:
        log_error("Failed to connect to MongoDB", e)
    except Exception as e:
        log_error("Unexpected error connecting to MongoDB", e)
    
    return index_model, collection

def upsert_to_pinecone(data, index_model, resource_type):
    """Upsert single data item to Pinecone."""
    if index_model is None or resource_type not in TEMPLATE_FUNCTIONS:
        return False
    
    try:
        # Create record
        record = {
            "id": data.get("gid"),
            "metadata": {
                "from": data.get("from", "Asana"),
                "client": data.get("client", []),
                "type": data.get("type", "general"),
                "gid": data.get("gid"),
                "resource_type": resource_type,
            }
        }
        
        # Generate text and embedding
        text = TEMPLATE_FUNCTIONS[resource_type](data)
        response = ai_client.embeddings.create(
            model='text-embedding-3-small',
            input=[text]
        )
        record["values"] = response.data[0].embedding
        
        # Upsert to Pinecone
        index_model.upsert([record], namespace=ENV)
        return True
    except Exception as e:
        log_error(f"Failed to upsert to Pinecone: {resource_type} {data.get('gid')}", e)
        return False

def upsert_to_mongodb(data, collection, resource_type):
    """Upsert single data item to MongoDB."""
    # if collection is None:
    #     return False
    
    try:
        # Convert datetime fields
        data_copy = convert_datetime_fields(copy.deepcopy(data))
        
        # Upsert to MongoDB
        collection.replace_one(
            {"gid": data_copy.get("gid"), "resource_type": resource_type},
            data_copy,
            upsert=True
        )
        return True
    except Exception as e:
        log_error(f"Failed to upsert to MongoDB: {resource_type} {data.get('gid')}", e)
        return False

def sync_upsert_data(data, index_model, collection, resource_type):
    """Synchronously upsert data to both databases."""
    if not isinstance(data, dict):
        return
    
    pinecone_success = upsert_to_pinecone(data, index_model, resource_type)
    mongodb_success = upsert_to_mongodb(data, collection, resource_type)
    
    if pinecone_success and mongodb_success:
        log_info(f"Successfully upserted {resource_type} {data.get('gid')} to both databases\n{json.dumps(data, indent=4)}")
    elif pinecone_success:
        log_error(f"Upserted to Pinecone only: {resource_type} {data.get('gid')}")
    elif mongodb_success:
        log_error(f"Upserted to MongoDB only: {resource_type} {data.get('gid')}")
    else:
        log_error(f"Failed to upsert to both databases: {resource_type} {data.get('gid')}")

class AsanaExporter:
    def __init__(self):
        self.space = {'updated': []}
        self.index_model, self.collection = setup_databases()

        self.setup()
        
    def setup(self):
        """Setup databases and logging."""
        setup_logging()
        # self.index_model, self.collection = setup_databases()
        log_info("AsanaExporter setup completed")
        
    def export_basic_data(self):
        """Export basic workspace data (workspace, teams, users, team_memberships)."""
        log_info("Starting basic data export...")
        
        # 1. Export workspace data
        try:
            log_info("Exporting workspace data...")
            response = get_response(API_INSTANCES['workspace'].get_workspaces, OPT_FIELDS['simple'])
            for workspace in tqdm(response, desc="Processing workspaces"):
                expand_data(workspace, self.space, None, self.index_model, self.collection)
            log_info(f"Exported {len(self.space.get('workspace', {}))} workspaces")
        except Exception as e:
            log_error("Failed to export workspace data", e)
        
        # 2. Export teams data
        try:
            log_info("Exporting teams data...")
            response = get_response(API_INSTANCES['team'].get_teams_for_workspace, WORKSPACE_ID, OPT_FIELDS['simple'])
            for team in tqdm(response, desc="Processing teams"):
                expand_data(team, self.space, None, self.index_model, self.collection)
            log_info(f"Exported {len(self.space.get('team', {}))} teams")
        except Exception as e:
            log_error("Failed to export teams data", e)
        
        # 3. Export users data
        try:
            log_info("Exporting users data...")
            response = get_response(API_INSTANCES['user'].get_users_for_workspace, WORKSPACE_ID, OPT_FIELDS['simple'])
            for user in tqdm(response, desc="Processing users"):
                expand_data(user, self.space, None, self.index_model, self.collection)
            log_info(f"Exported {len(self.space.get('user', {}))} users")
        except Exception as e:
            log_error("Failed to export users data", e)
        
        # 4. Export team_memberships data
        try:
            log_info("Exporting team memberships data...")
            all_memberships = []
            for team_gid in self.space.get('team', {}):
                try:
                    response = get_response(API_INSTANCES['team_membership'].get_team_memberships_for_team, 
                                          team_gid, OPT_FIELDS['simple'])
                    all_memberships.extend(response)
                except Exception as e:
                    log_error(f"Failed to get memberships for team {team_gid}", e)
            
            for membership in tqdm(all_memberships, desc="Processing team memberships"):
                expand_data(membership, self.space, None, self.index_model, self.collection)
            log_info(f"Exported {len(self.space.get('team_membership', {}))} team memberships")
        except Exception as e:
            log_error("Failed to export team memberships data", e)
        
        log_info("Basic data export completed")

    # import_projects = ["009. HelloCash | PPC",
    #     "013. Event Inc | PPC",
    #     "029. Kitbash3d | SOC",
    #     "030. Nano Hearing Aids | S&E",
    #     "042. MyTrueAncestry | S&E",
    #     "045. FoodMarble | Interim",
    #     "053. Oviva",
    #     "053. Oviva | Interim",
    #     "064. ISC-CX | ALL",
    #     "069. Inge Rock | PPC",
    #     "071. Emost | SOC",
    #     "075. Dr. Peter Dobias | Execution",
    #     "084. Proxify | PPC",
    #     "092. Deezer",
    #     "103. VitHit | PPC",
    #     "107. Rebaid | S&E",
    #     "109. Treehut | EXE",
    #     "110. Behavioural Design | Strategy and Execution",
    #     "113. Essentra | PPC",
    #     "118. K9TI | Paid Social",
    #     "119. Stage Entertainment | Interim",
    #     "123. H2O | ALL",
    #     "124. Hint | PPC",
    #     "125. Match Talent | EXE",
    #     "127. Yamamoto | S&E",
    #     "128. Ritzy Charters | S&E",
    #     "129. Able | PPC",
    #     "132. Connected Culture | EXE",
    #     "133. HelloGina | Strategy and Execution",
    #     "134. B.O.S.S. | Strategy and Execution",
    #     "136. Soly | 1:1 Sessions",
    #     "137. Envest | PPC",
    #     "138. Le Falaf | Strategy and Execution",
    #     "139. StartSteps | PPC",
    #     "140. Hello World | S&E",
    #     "141. Beam Insititute | S&E",
    #     "142. YouWish | PPC",
    #     "143. SchoolStatus | S&E",
    #     "144. Ashera | S&E",
    #     "145. Match Pflege | S&E",
    #     "146. Assivo | Strategy & Execution",
    #     "147. | TheNewCo | Google Ads",
    #     "147. The NewCo | 121",
    #     "148. Zwilling | SOC",
    #     "149. EasyMorph | S&E",
    #     "150. Jottacloud | S&E",
    #     "152. Piano University | S&E",
    #     "153. Filemail | PPC",
    #     "154. My IQ | PPC",
    #     "155. Gismart | PPC",
    #     "156. DatingSphere | S&E",
    #     "157. Oviva UK | ALL",
    #     "158. Displate | AUD",
    #     "159. Moonfare | Interim",
    #     "160. MyTutor | S&E",
    #     "162. Local Beach | S&E",
    #     "163. Clarity Check | PPC",
    #     "164. Roompot & Landal | RES",
    #     "165. ImmoScout24 | PPC",
    #     "166. ControlPlane | S&E",
    #     "167. Love Thrive | PPC",
    #     "168. Microfeller | S&E",
    #     "169. Aspect Health | PPC",
    #     "170. Awaken180 | S&E",
    #     "171. Dr. Beasley's | PPC",
    #     "172. BioBuilds | PPC",
    #     "173. Flex Pricing | S&E",
    #     "174. Tofu | PPC",
    #     "175. Fingreen AI | S&E",
    #     "176. Dragon Digital | PPC",
    #     "177. ZenDocs | PPC",
    #     "179. GIK Acoustics | S&E",
    #     "180. WildLovers | S&E",
    #     "181. Sesterce | S&E",
    #     "182. Seoul Onni | ALL",
    #     "183. Stellans | S&E",
    #     "184. YieldSchool | ALL"
    # ]

    def export_projects_data(self):
        """Export projects data."""
        log_info("Starting projects data export...")
        
        try:
            response = get_response(API_INSTANCES['project'].get_projects_for_workspace, WORKSPACE_ID, {'opt_fields': 'gid,resource_type,name'})
            projects = list(response)

            for project in tqdm(projects, desc="Processing projects"):
                if not project["name"][:3].isnumeric():
                    continue
                try:
                    expand_data(project, self.space, None, self.index_model, self.collection)
                    if project.get('gid') in self.space.get('project', {}):
                        project_data = self.space['project'][project['gid']]
                        # Log project info
                        project_name = project_data.get('name', 'Unknown')
                        log_info(f"Exported project: {project_name}")
                except Exception as e:
                    log_error(f"Failed to export project {project.get('gid', 'unknown')}", e)
            
            log_info(f"Exported {len(self.space.get('project', {}))} projects")
        except Exception as e:
            log_error("Failed to export projects data", e)
    
    def process_task_recursively(self, task_gid, client_ids, project_name, depth=0):
        """Recursively process a task and all its subtasks."""
        task_count = 0
        story_count = 0
        subtask_count = 0
        
        try:
            # Get task data
            task_data = {'gid': task_gid, 'resource_type': 'task'}
            expand_data(task_data, self.space, client_ids, self.index_model, self.collection)
            
            if task_gid in self.space.get('task', {}):
                task_count += 1
                task_full_data = self.space['task'][task_gid]
                task_name = task_full_data.get('name', 'Unknown Task')
                
                log_info(f"{'  ' * depth}Processing task: {task_name} (depth: {depth})")
                
                # Export stories for this task
                try:
                    stories_response = get_response(API_INSTANCES['story'].get_stories_for_task, task_gid, {'opt_fields': 'gid,resource_type'})
                    for story in stories_response:
                        try:
                            expand_data(story, self.space, client_ids, self.index_model, self.collection)
                            if story.get('gid') in self.space.get('story', {}):
                                story_count += 1
                        except Exception as e:
                            log_error(f"Failed to process story {story.get('gid', 'unknown')} for task {task_gid}", e)
                except Exception as e:
                    log_error(f"Failed to get stories for task {task_gid}", e)
                
                # Get and process subtasks recursively
                try:
                    # Check if the task has subtasks before making API call
                    num_subtasks = task_full_data.get('num_subtasks', 0)
                    if num_subtasks > 0:
                        api = asana.TasksApi(api_client).get_subtasks_for_task
                        subtasks_response = get_response(api, task_gid, {'opt_fields': 'gid,resource_type'})
                        # subtasks_response = get_response(API_INSTANCES['task'].get_subtasks_for_task, task_gid, OPT_FIELDS['simple'])
                        subtasks = list(subtasks_response)
                        
                        if subtasks:
                            log_info(f"{'  ' * depth}Found {len(subtasks)} subtasks for task: {task_name}")
                        
                        for subtask in subtasks:
                            try:
                                # Prevent infinite recursion by limiting depth
                                if depth < 10:  # Maximum depth of 10 levels
                                    # Recursively process each subtask
                                    sub_task_count, sub_story_count, sub_subtask_count = self.process_task_recursively(
                                        subtask['gid'], client_ids, project_name, depth + 1
                                    )
                                    task_count += sub_task_count
                                    story_count += sub_story_count
                                    subtask_count += sub_subtask_count + 1  # +1 for the current subtask
                                else:
                                    log_error(f"Maximum recursion depth reached for task {task_gid}, skipping deeper subtasks")
                            except Exception as e:
                                log_error(f"Failed to process subtask {subtask.get('gid', 'unknown')} for task {task_gid}", e)
                    else:
                        log_info(f"{'  ' * depth}Task {task_name} has no subtasks")
                            
                except Exception as e:
                    log_error(f"Failed to get subtasks for task {task_gid}", e)
                    
        except Exception as e:
            log_error(f"Failed to process task {task_gid}", e)
            
        return task_count, story_count, subtask_count

    def process_single_project(self, project_gid, project_name):
        """Process a single project in a thread."""
        try:
            log_info(f"Starting thread for project: {project_name}")
            
            # Get project data to extract client info
            project_data = self.space.get('project', {}).get(project_gid)
            if not project_data:
                log_error(f"Project data not found for {project_gid}")
                return
            
            client_ids = project_data.get('client', [])
            
            # Export tasks for this project (top-level tasks only)
            total_task_count = 0
            total_story_count = 0
            total_subtask_count = 0
            
            try:
                api = asana.TasksApi(api_client).get_tasks_for_project
                tasks_response = get_response(api, project_gid, {'opt_fields': 'gid,resource_type'})
                # tasks_response = get_response(API_INSTANCES['task'].get_tasks_for_project, project_gid, OPT_FIELDS['simple'])
                tasks = list(tasks_response)
                
                log_info(f"Project {project_name}: Found {len(tasks)} top-level tasks")
                
                for task in tasks:
                    try:
                        # Process each task and all its subtasks recursively
                        task_count, story_count, subtask_count = self.process_task_recursively(
                            task['gid'], client_ids, project_name, depth=0
                        )
                        total_task_count += task_count
                        total_story_count += story_count
                        total_subtask_count += subtask_count
                        
                    except Exception as e:
                        log_error(f"Failed to process task {task.get('gid', 'unknown')} for project {project_gid}", e)
                
                log_info(f"Project {project_name}: Exported {total_task_count} tasks (including {total_subtask_count} subtasks) and {total_story_count} stories")
            except Exception as e:
                log_error(f"Failed to get tasks for project {project_gid}", e)
            
            # Export sections for this project
            section_count = 0
            try:
                api = asana.SectionsApi(api_client).get_sections_for_project
                sections_response = get_response(api, project_gid, {'opt_fields': 'gid,resource_type'})
                # sections_response = get_response(API_INSTANCES['section'].get_sections_for_project, project_gid, OPT_FIELDS['simple'])
                for section in sections_response:
                    try:
                        expand_data(section, self.space, client_ids, self.index_model, self.collection)
                        if section.get('gid') in self.space.get('section', {}):
                            section_count += 1
                    except Exception as e:
                        log_error(f"Failed to process section {section.get('gid', 'unknown')} for project {project_gid}", e)
                
                log_info(f"Project {project_name}: Exported {section_count} sections")
            except Exception as e:
                log_error(f"Failed to get sections for project {project_gid}", e)
            
            # Export status updates for this project
            status_update_count = 0
            try:
                api = asana.StatusUpdatesApi(api_client).get_statuses_for_object
                status_updates_response = get_response(api, project_gid, {'opt_fields': 'gid,resource_type'})
                # status_updates_response = get_response(API_INSTANCES['status_update'].get_statuses_for_object, project_gid, OPT_FIELDS['simple'])
                for status_update in status_updates_response:
                    try:
                        expand_data(status_update, self.space, client_ids, self.index_model, self.collection)
                        if status_update.get('gid') in self.space.get('status_update', {}):
                            status_update_count += 1
                    except Exception as e:
                        log_error(f"Failed to process status update {status_update.get('gid', 'unknown')} for project {project_gid}", e)
                
                log_info(f"Project {project_name}: Exported {status_update_count} status updates")
            except Exception as e:
                log_error(f"Failed to get status updates for project {project_gid}", e)
            
            # Export project template if applicable
            if project_data.get('created_from_template'):
                try:
                    template_gid = project_data['created_from_template'].get('gid')
                    if template_gid:
                        expand_data(project_data['created_from_template'], self.space, None, self.index_model, self.collection)
                        if template_gid in self.space.get('project_template', {}):
                            log_info(f"Project {project_name}: Exported project template")
                except Exception as e:
                    log_error(f"Failed to process project template for project {project_gid}", e)
            
            log_info(f"Completed thread for project: {project_name}")
            
        except Exception as e:
            log_error(f"Critical error in project thread for {project_name}", e)
    
    def export_project_details(self):
        """Export detailed data for all projects using thread pool."""
        log_info("Starting detailed project export with threading...")
        
        projects = self.space.get('project', {})
        if not projects:
            log_info("No projects found to process")
            return
        
        # Create list of project info for threading
        project_info = [(gid, data.get('name', f'Project-{gid}')) for gid, data in projects.items()]
        
        max_workers = 20
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all project processing tasks
            future_to_project = {
                executor.submit(self.process_single_project, project_gid, project_name): (project_gid, project_name)
                for project_gid, project_name in project_info
            }
            
            # Process completed tasks with progress bar
            with tqdm(total=len(project_info), desc="Processing projects") as pbar:
                for future in as_completed(future_to_project):
                    project_gid, project_name = future_to_project[future]
                    try:
                        future.result()  # This will raise any exception that occurred
                        completed_count += 1
                    except Exception as e:
                        log_error(f"Project thread failed for {project_name} ({project_gid})", e)
                    finally:
                        pbar.update(1)
        
        log_info(f"Completed detailed export for {completed_count}/{len(project_info)} projects")
    
    def run_export(self):
        """Run the complete export process."""
        log_info("=== Starting Comprehensive Asana Export ===")
        
        try:
            # Setup databases
            self.setup()
            
            # Step 1-4: Export basic data
            self.export_basic_data()
            
            # Step 5: Export projects data
            self.export_projects_data()
            
            # Step 6: Export detailed project data with threading
            self.export_project_details()
            
            # Summary
            summary = {
                'workspaces': len(self.space.get('workspace', {})),
                'teams': len(self.space.get('team', {})),
                'users': len(self.space.get('user', {})),
                'team_memberships': len(self.space.get('team_membership', {})),
                'projects': len(self.space.get('project', {})),
                'tasks': len(self.space.get('task', {})),
                'stories': len(self.space.get('story', {})),
                'sections': len(self.space.get('section', {})),
                'status_updates': len(self.space.get('status_update', {})),
                'project_templates': len(self.space.get('project_template', {})),
            }
            
            log_info("=== Export Summary ===")
            for resource_type, count in summary.items():
                log_info(f"{resource_type}: {count}")
            
            log_info("=== Comprehensive Asana Export Completed Successfully ===")

            return summary
            
        except Exception as e:
            log_error("Critical error in export process", e)
            raise

global_exporter = AsanaExporter()

# def main():
#     """Main function to run the export."""
#     exporter = AsanaExporter()
#     exporter.run_export()