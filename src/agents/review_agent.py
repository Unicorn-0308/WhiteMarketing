import copy, json
import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage

from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, func_process_task
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
    today = datetime.date.today().strftime('%Y-%m-%d')
    client = json.dumps(state['client'], indent=4)

    project = copy.deepcopy(state['project'])
    project['created_at'] = project['created_at'].strftime("%Y-%m-%d %H:%M:%S")
    project['modified_at'] = project['modified_at'].strftime("%Y-%m-%d %H:%M:%S")
    if project['due_on']:
        project['due_on'] = project['due_on'].strftime("%Y-%m-%d %H:%M:%S")
    if project['due_date']:
        project['due_date'] = project['due_date'].strftime("%Y-%m-%d %H:%M:%S")
    project = json.dumps(project, indent=4)

    weekly_reviews = copy.deepcopy(state['weekly'])
    monthly_reviews = copy.deepcopy(state['monthly'])
    weekly = ''
    monthly = ''
    for group in [weekly_reviews, monthly_reviews]:
        for review in group:
            review['updatedAt'] = review['updatedAt'].strftime("%Y-%m-%d %H:%M:%S")
            if review['date'] != '':
                review['date'] = review['date'].strftime("%Y-%m-%d")
            weekly += f"{'Weekly' if review['type'] == 'weekly' else 'Monthly'} Review on {review['date']}\n{json.dumps(review, indent=4)}\n"
            del review['type']

    tasks = copy.deepcopy(state['tasks'])
    tasks = sorted(tasks, key=lambda item: item['created_at'])
    for task in tasks:
        for date in ["created_at", "completed_at", "due_on", "due_date", "modified_at"]:
            if date in task and task[date] is not None:
                try:
                    task[date] = task[date].strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(date, task[date])
        try:
            json.dumps(task)
        except Exception as e:
            print(e, task)
    completed_tasks = []
    active_tasks = []
    for task in tasks:
        if task['completed']:
            completed_tasks.append(task)
        else:
            active_tasks.append(task)
    completed_tasks = json.dumps(completed_tasks[max(0, len(completed_tasks) - 20):], indent=4)
    active_tasks = json.dumps(active_tasks, indent=4)

    prompt = get_prompt_template(PromptTemplate.REVIEW_GEN).format(
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
    return {'messages': [AIMessage(final_text)]}

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
        "messages": [{"role": "user", "content": "Hello!"}],
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