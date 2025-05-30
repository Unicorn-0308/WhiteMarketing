import copy, json
import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer

from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, func_process_task, func_get_response
from src.models.review import ReviewGenState, TaskState
from src.utils import llm
from db import mongo
from config import PromptTemplate, get_prompt_template, llm_model


# Nodes
def get_client(state: ReviewGenState, config: RunnableConfig):
    return func_get_client(state['clientId'], agent="review_gen")

def get_project(state: ReviewGenState, config: RunnableConfig):
    return func_get_project(state['clientId'], agent="review_gen")

def get_reviews(state: ReviewGenState, config: RunnableConfig):
    return func_get_reviews(state['clientId'], agent="review_gen")

def get_tasks(state: ReviewGenState, config: RunnableConfig):
    return func_get_tasks(state['clientId'], agent="review_gen")

def process_task(state: TaskState, config: RunnableConfig):
    return func_process_task(state['task'], agent="review_gen")

def synthesizer(state: ReviewGenState, config: RunnableConfig):
    return {}

def get_response(state: ReviewGenState, config: RunnableConfig):
    ## Process context data
    today, project, weekly_reviews, monthly_reviews, completed_tasks, active_tasks = func_get_response(state, "review_gen")

    client = json.dumps(state['client'], indent=4)
    project = json.dumps(project, indent=4)

    weekly = ''
    for review in weekly_reviews:
        weekly += f"Weekly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"
    monthly = ''
    for review in monthly_reviews:
        monthly += f"Monthly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"

    completed_tasks = json.dumps(completed_tasks[max(0, len(completed_tasks) - 20):], indent=4)
    active_tasks = json.dumps(active_tasks, indent=4)

    prompt = get_prompt_template(PromptTemplate.REVIEW_GEN)
    prompt = prompt.format(
        today=today,
        client_data=client,
        project_data=project,
        weekly_reviews=weekly,
        monthly_reviews=monthly,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks,
    )

    writer = get_stream_writer()
    stream = llm.responses.create(
        model=llm_model["review"],
        input=[{
            'role': 'developer',
            'content': prompt,
        }],
        stream=True
    )
    final_text = ''
    for event in stream:
        if event.type == 'response.output_text.delta':
            final_text += event.delta
            writer({'delta': event.delta, 'position': 'final_response'})
    return {}

# Conditional Edges
def continue_to_task(state: ReviewGenState, config: RunnableConfig):
    return [Send('process_task', {'task': task}) for index, task in enumerate(state['raw_tasks'])]


# Setup Graph
def setup_graph():
    graph_builder = StateGraph(ReviewGenState)

    graph_builder.add_node(get_client)
    graph_builder.add_node(get_project)
    graph_builder.add_node(get_reviews)
    graph_builder.add_node(get_tasks)
    graph_builder.add_node(process_task)
    graph_builder.add_node(synthesizer)
    graph_builder.add_node(get_response)

    graph_builder.add_edge(START, 'get_client')
    graph_builder.add_edge(START, 'get_project')
    graph_builder.add_edge(START, 'get_reviews')
    graph_builder.add_edge(START, 'get_tasks')
    graph_builder.add_edge('get_client', 'synthesizer')
    graph_builder.add_edge('get_project', 'synthesizer')
    graph_builder.add_edge('get_reviews', 'synthesizer')
    graph_builder.add_edge('get_tasks', 'synthesizer')
    graph_builder.add_conditional_edges('synthesizer', continue_to_task, {'process_task': 'process_task'})
    graph_builder.add_edge('process_task', 'get_response')
    graph_builder.add_edge('get_response', END)

    return graph_builder


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv('./../../.env')

    graph = setup_graph().compile()  # graph is compiled in setup_graph now
    code = graph.get_graph().draw_mermaid()
    print(code)

    initial_state = {
        "clientId": "179",
        "tasks": [],
    }

    # Stream with configuration to see full state updates
    configuration = {"recursion_limit": 100, "configurable": {"thread_id": "test-thread"}}
    for event_part in graph.stream(initial_state, config=configuration, stream_mode="updates"):
        # event_part is a dictionary where keys are node names and values are their output
        print(f"--- Graph Update ---")
        for node_name, output in event_part.items():
            print(f"Node '{node_name}'")
            # if node_name == "process_task" and "tasks" in output:
            #     print(f"  ^^^ process_task produced tasks, this should trigger accumulator.")
        # To see the full state after each update, you'd need to inspect the graph's internal state
        # or rely on the final event from get_response.

    print("\n--- Final state (from a final invocation if needed, or inspect last event) ---")