import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

class TaskGenState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    clientId: str
    client: Dict[str, Any]
    project: Dict[str, Any]
    tasks: Annotated[List[Dict[str, Any]], operator.add]
    weekly: Annotated[List[Dict[str, Any]], operator.add]
    monthly: Annotated[List[Dict[str, Any]], operator.add]

class TaskState(TypedDict):
    task: Dict[str, Any]