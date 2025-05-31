import copy, json
import datetime
from dotenv import load_dotenv
load_dotenv('./../../.env')

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage
from db import mongo

from config import PromptTemplate, get_prompt_template, llm_model
from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, \
    func_process_task, func_get_response
from src.models.task import TaskGenState, TaskState, Task
from src.utils import llm


# Nodes
def get_client(state: TaskGenState, config: RunnableConfig):
    client = func_get_client(state['clientId'], agent="task_gen")
    data = list(mongo.find({ 'type': "client_spec", 'client': "009", 'from': "Slite", 'content': {'$ne': ""} }))
    client_spec = ''
    for note in data:
        client_spec += f"# {note['title']}\n{json.dumps(note['sections'], indent=4)}\n\n"

    summary = llm.chat.completions.create(
        model=llm_model['summarize'],
        messages=[{"role": "system", "content": get_prompt_template(PromptTemplate.CLIENT_SUMMARIZE).format(client=json.dumps(client['client'], indent=4), client_spec=client_spec.strip())}]
    ).choices[0].message.content

    return { 'clientId': client['clientId'], 'client_spec': summary }

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
    today, project, weekly_reviews, monthly_reviews, completed_tasks, active_tasks = func_get_response(state, "task_gen")

    project = json.dumps(project, indent=4)

    weekly = ''
    for review in weekly_reviews[max(0, len(weekly_reviews) - 5):]:
        weekly += f"Weekly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"
    monthly = ''
    for review in monthly_reviews[max(0, len(weekly_reviews) - 5):]:
        monthly += f"Monthly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"

    completed_tasks = json.dumps(completed_tasks[max(0, len(weekly_reviews) - 100):], indent=4)
    active_tasks = json.dumps(active_tasks, indent=4)

    prompt = get_prompt_template(PromptTemplate.TASK_INFO_GEN)
    prompt = prompt.format(
        today=today,
        description=state['description'],
        client_spec=state['client_spec'],
        project_data=project,
        weekly_reviews=weekly,
        monthly_reviews=monthly,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks,
    )

    writer = get_stream_writer()
    stream = llm.responses.create(
        model=llm_model["task"],
        input=[{
            'role': 'developer',
            'content': prompt,
        }],
        stream=True,
    )
    final_text = ''
    for event in stream:
        if event.type == 'response.output_text.delta':
            final_text += event.delta
            writer({'delta': event.delta, 'position': 'final_response'})

    prompt = get_prompt_template(PromptTemplate.TASK_GEN)
    prompt = prompt.format(
        today=today,
        description=state['description'],
        client_spec=state['client_spec'],
        project_data=project,
        weekly_reviews=weekly,
        monthly_reviews=monthly,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks,
    )
    task = llm.responses.parse(
        model=llm_model["task"],
        input=[{
            'role': 'developer',
            'content': prompt,
        }],
        text_format=Task
    ).output_parsed
    writer({'task': task, 'position': 'final_task'})

    return {}


# Conditional Edges
def continue_to_task(state: TaskGenState, config: RunnableConfig):
    return [Send('process_task', {'task': task}) for index, task in enumerate(state['raw_tasks'])]


# Setup Graph
def setup_graph():
    graph_builder = StateGraph(TaskGenState)

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

    graph = setup_graph().compile()  # graph is compiled in setup_graph now
    code = graph.get_graph().draw_mermaid()
    print(code)

    initial_state = {
        "clientId": "009",
        "description": "Create a task for the client to complete.",
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