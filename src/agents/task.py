import copy, json
import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage


# Setup Graph
def setup_graph():
    graph_builder = StateGraph()