import copy, json
import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage
from db import mongo

from config import PromptTemplate, get_prompt_template, llm_model
from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, func_process_task
from src.models.task import TaskGenState, TaskState


# Nodes
def get_client(state: TaskGenState, config: RunnableConfig):
    return func_get_client(state['clientId'], agent="task_gen")

def get_project(state: TaskGenState, config: RunnableConfig):
    return func_get_project(state['clientId'], agent="task_gen")

def get_reviews(state: TaskGenState, config: RunnableConfig):
    return func_get_reviews(state['clientId'], agent="task_gen")

def get_tasks(state: TaskGenState, config: RunnableConfig):
    return func_get_tasks(state['clientId'], agent="task_gen")

def process_task(state: TaskState, config: RunnableConfig):
    return func_process_task(state['task'], agent="task_gen")

def synthesizer(state: TaskGenState, config: RunnableConfig):
    return {}

def get_response(state: TaskGenState, config: RunnableConfig):
    ## Process context data
    today = datetime.date.today().strftime('%Y-%m-%d')


    pass


# Conditional Edges
def continue_to_task(state: TaskGenState, config: RunnableConfig):
    return [Send('process_task', {'task': task}) for index, task in enumerate(state['raw_tasks'])]


# Setup Graph
def setup_graph():
    graph_builder = StateGraph(TaskGenState)