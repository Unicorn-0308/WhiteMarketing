import operator
from typing import Annotated, TypedDict, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class GeneralState(TypedDict):
    clientId: str
    client_spec: str
    project: Dict[str, Any]
    raw_tasks: Annotated[List[Dict[str, Any]], operator.add]
    tasks: Annotated[List[Dict[str, Any]], operator.add]
    weekly: Annotated[List[Dict[str, Any]], operator.add]
    monthly: Annotated[List[Dict[str, Any]], operator.add]
    messages: Annotated[List[BaseMessage], add_messages]
    tools: List[Dict[str, Any]]
    datas: Annotated[List[Dict[str, Any]], operator.add]

class TaskState(TypedDict):
    task: Dict[str, Any]

class ToolState(TypedDict):
    purpose: str
    tool: Dict[str, Any]