import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional, Literal, Union
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import add_messages
from pydantic import BaseModel, Field, ConfigDict

class MongoFilter(BaseModel):
    filter: Dict[str, Any] = Field(..., description='This is mongoDB filter object for python')
    sort: List[Dict[str, int]] = Field(..., description='This is mongoDB sort object for python, not empty.')
    limit: int = Field(..., description='This is mongoDB limit object for python')

class MongoAggregation(BaseModel):
    pipeline: List[Dict[str, Any]] = Field(..., description='This is mongoDB aggregation stages list for python')

class PineconeQuery(BaseModel):
    query: str = Field(..., description='This is pinecone query string')
    top_k: int = Field(..., description='This is pinecone top_k')
    meta_filter: Optional[dict] = Field(..., description='This is pinecone metadata filter')

class Tool(BaseModel):
    purpose: str = Field(..., description='This is the purpose to use the tool.')
    tool: Literal["mongo_filter", "mongo_aggregation", "pinecone_search"] = Field(..., description='This is tool name to use')
    param: Union[MongoFilter, MongoAggregation, PineconeQuery] = Field(description='This is tool params')

class Tools(BaseModel):
    tools: List[Tool] = Field(..., description='This is tools list')

class GeneralState(TypedDict):
    clientId: str
    client_spec: str
    project: Dict[str, Any]
    raw_tasks: Annotated[List[Dict[str, Any]], operator.add]
    tasks: Annotated[List[Dict[str, Any]], operator.add]
    weekly: Annotated[List[Dict[str, Any]], operator.add]
    monthly: Annotated[List[Dict[str, Any]], operator.add]
    messages: Annotated[List[BaseMessage], add_messages]
    tools: Tools
    datas: Annotated[List[Dict[str, Any]], operator.add]

class TaskState(TypedDict):
    task: Dict[str, Any]

class ToolState(TypedDict):
    purpose: str
    tool: Union[MongoFilter, MongoAggregation, PineconeQuery]