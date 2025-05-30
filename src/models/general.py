import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional, Literal, Union
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool
from langgraph.graph import add_messages
from pydantic import BaseModel, Field, ConfigDict

class MongoFilter(BaseModel):
    purpose: str = Field(..., description='This is the purpose to use the tool.')
    filter: Dict[str, Any] = Field(..., description='This is mongoDB filter object for python')
    sort: List[Dict[str, int]] = Field(..., description='This is mongoDB sort object for python, not empty.')
    limit: int = Field(..., description='This is mongoDB limit object for python')

class MongoAggregation(BaseModel):
    purpose: str = Field(..., description='This is the purpose to use the tool.')
    pipeline: List[Dict] = Field(..., description='This is mongoDB aggregation stages list for python', strict=False)

    # class Config:
    #     additionalProperties = False

    model_config = ConfigDict(extra='forbid')

class PineconeQuery(BaseModel):
    purpose: str = Field(..., description='This is the purpose to use the tool.')
    query: str = Field(..., description='This is pinecone query string')
    top_k: int = Field(..., description='This is pinecone top_k')
    meta_filter: Optional[dict] = Field(..., description='This is pinecone metadata filter')

class Tool(BaseModel):
    tool: Literal["mongo_filter", "mongo_aggregation", "pinecone_search"] = Field(..., description='This is tool name to use')
    param: Union[MongoFilter, MongoAggregation, PineconeQuery] = Field(description='This is tool params')

class Tools(BaseModel):
    tools: List[Tool] = Field(..., description='This is tools list')

Tools_ = {
    "$defs": {
        "MongoAggregation": {
            "properties": {
                "purpose": {
                    "default": "",
                    "description": "This is the purpose to use the tool.",
                    "title": "Purpose",
                    "type": "string"
                },
                "pipeline": {
                    "default": [],
                    "description": "This is mongoDB aggregation stages list for python",
                    "items": {
                        "additionalProperties": True,
                        "type": "object"
                    },
                    "title": "Pipeline",
                    "type": "array"
                }
            },
            "title": "MongoAggregation",
            "type": "object"
        },
        "MongoFilter": {
            "properties": {
                "purpose": {
                    "default": "",
                    "description": "This is the purpose to use the tool.",
                    "title": "Purpose",
                    "type": "string"
                },
                "filter": {
                    "additionalProperties": True,
                    "description": "This is mongoDB filter object for python",
                    "title": "Filter",
                    "type": "object"
                },
                "sort": {
                    "default": [
                        [
                            "date",
                            -1
                        ],
                        [
                            "created_at",
                            -1
                        ]
                    ],
                    "description": "This is mongoDB sort object for python, not empty.",
                    "items": {
                        "additionalProperties": {
                            "type": "integer"
                        },
                        "type": "object"
                    },
                    "title": "Sort",
                    "type": "array"
                },
                "limit": {
                    "default": 10,
                    "description": "This is mongoDB limit object for python",
                    "title": "Limit",
                    "type": "integer"
                }
            },
            "title": "MongoFilter",
            "type": "object"
        },
        "PineconeQuery": {
            "properties": {
                "purpose": {
                    "default": "",
                    "description": "This is the purpose to use the tool.",
                    "title": "Purpose",
                    "type": "string"
                },
                "query": {
                    "default": "",
                    "description": "This is pinecone query string",
                    "title": "Query",
                    "type": "string"
                },
                "top_k": {
                    "default": 10,
                    "description": "This is pinecone top_k",
                    "title": "Top K",
                    "type": "integer"
                },
                "meta_filter": {
                    "anyOf": [
                        {
                            "additionalProperties": True,
                            "type": "object"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": {},
                    "description": "This is pinecone metadata filter",
                    "title": "Meta Filter"
                }
            },
            "title": "PineconeQuery",
            "type": "object"
        },
        "Tool": {
            "properties": {
                "tool": {
                    "default": "",
                    "description": "This is tool name to use",
                    "enum": [
                        "mongo_filter",
                        "mongo_aggregation",
                        "pinecone_search"
                    ],
                    "title": "Tool",
                    "type": "string"
                },
                "param": {
                    "anyOf": [
                        {
                            "$ref": "#/$defs/MongoFilter"
                        },
                        {
                            "$ref": "#/$defs/MongoAggregation"
                        },
                        {
                            "$ref": "#/$defs/PineconeQuery"
                        }
                    ],
                    "description": "This is tool params",
                    "title": "Param"
                }
            },
            "required": [
                "param"
            ],
            "title": "Tool",
            "type": "object"
        }
    },
    "properties": {
        "tools": {
            "default": [],
            "description": "This is tools list",
            "items": {
                "$ref": "#/$defs/Tool"
            },
            "title": "Tools",
            "type": "array"
        }
    },
    "title": "Tools",
    "type": "object"
}

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
    tool: Union[MongoFilter, MongoAggregation, PineconeQuery]