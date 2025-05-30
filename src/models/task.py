import operator
from typing import Annotated, TypedDict, List, Dict, Any
from pydantic import BaseModel, Field

class CustomField(BaseModel):
    name: str = Field("", description="The name of the custom field.")
    value: str = Field("", description="The value of the custom field.")

class Task(BaseModel):
    assignee: str = Field("", description="A user object represents an account in Asana that can be given access to various workspaces, projects, and tasks.")
    custom_fields: List[CustomField] = Field([], description="Array of custom field values applied to the task. These represent the custom field values recorded on this project for a particular custom field. For example, these custom field values will contain an enum_value property for custom fields of type enum, a text_value property for custom fields of type text, and so on.")
    due_on: str = Field("", description="The localized date on which this task is due, or null if the task has no due date. This takes a date with YYYY-MM-DD.")
    section: str = Field("", description="A section is a subdivision of a project that groups tasks together. It can either be a header above a list of tasks in a list view or a column in a board view of a project.")
    name: str = Field("", description="Name of the task. This is generally a short sentence fragment that fits on a line in the UI for maximum readability. However, it can be longer.")
    notes: str = Field("", description="Free-form textual information associated with the task (i.e. its description).")
    tags: List[str] = Field([], description="The tags are marketing tools such as Google Search and Facebook Ads that you use in the task.")

class TaskGenState(TypedDict):
    clientId: str
    description: str
    client_spec: str
    project: Dict[str, Any]
    raw_tasks: Annotated[List[Dict[str, Any]], operator.add]
    tasks: Annotated[List[Dict[str, Any]], operator.add]
    weekly: Annotated[List[Dict[str, Any]], operator.add]
    monthly: Annotated[List[Dict[str, Any]], operator.add]
    task: Task

class TaskState(TypedDict):
    task: Dict[str, Any]
