import copy, json
import datetime

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage

from src.models.review import ReviewState, TaskState
from src.utils import llm
from db import mongo
from config import PromptTemplate, get_prompt_template, llm_model

import tiktoken
encoding = tiktoken.encoding_for_model(llm_model['review'])

# Nodes
def get_client(state: ReviewState, config: RunnableConfig):
    client = mongo.find_one({"gid": state['clientId']})
    return {'client': client, 'clientId': client['gid']}

def get_project(state: ReviewState, config: RunnableConfig):
    project = mongo.find_one({"resource_type": 'project', "client": state['clientId']})
    attachments = list(mongo.find({"resource_type": 'attachment', "client": state['clientId'], "parent.gid": project['gid']}))
    project['attachments'] = attachments
    del project['_id'], project['gid'], project['color'], project['custom_fields'], project['custom_field_settings'], project['default_access_level'],\
        project['default_view'], project['minimum_access_level_for_customization'], project['minimum_access_level_for_sharing'], project['permalink_url'], project['privacy_setting'], \
        project['resource_type'], project['workspace'], project['html_notes'], project['created_from_template'], project['from'], project['type'], project['client']
    project['team'] = project['team']['name'] if project['team'] else ''
    project['owner'] = project['owner']['name'] if project['owner'] else ''
    project['followers'] = [follower['name'] for follower in project['followers']]
    project['members'] = [member['name'] for member in project['members']]

    return {'project': project}

def get_reviews(state: ReviewState, config: RunnableConfig):
    weekly_reviews = list(mongo.find({'type': 'weekly', "client": state['clientId']}).sort(['date']))
    monthly_reviews = list(mongo.find({'type': 'monthly', "client": state['clientId']}).sort(['date']))
    for group in [weekly_reviews, monthly_reviews]:
        for review in group:
            del review['_id'], review['sections'], review['client'], review['from'], review['children'], review['parentNoteId'], review['id']
    return {'weekly': weekly_reviews, 'monthly': monthly_reviews}

def get_tasks(state: ReviewState, config: RunnableConfig):
    tasks = list(mongo.aggregate([
        {
            '$match': {
                'resource_type': 'task',
                'client': state['clientId'],
            }
        }, {
            '$lookup': {
                'from': 'mvp',
                'localField': 'gid',
                'foreignField': 'target.gid',
                'as': 'stories',
                'pipeline': [
                    {
                        '$match': {
                            'resource_type': 'story'
                        }
                    }, {
                        '$sort': {
                            'created_at': 1
                        }
                    }
                ]
            }
        }, {
            '$lookup': {
                'from': 'mvp',
                'localField': 'gid',
                'foreignField': 'parent.gid',
                'as': 'attachments',
                'pipeline': [
                    {
                        '$match': {
                            'resource_type': 'attachment'
                        }
                    }
                ]
            }
        }, {
            '$sort': {
                'created_at': 1
            }
        }
    ]))

    return {
        'raw_tasks': tasks
    }

def process_task(state: TaskState):
    task = state['task']
    del task['_id'], task['html_notes'], task['hearts'], task['likes'], task['projects'], task['workspace'], task['created_by'], task['client'], task['from'], task['type']
    task['assignee'] = task['assignee']['name'] if task['assignee'] else ''
    task['custom_fields'] = [{
        'name': cf['name'],
        'value': cf['display_value']
    } for cf in task['custom_fields']]
    task['followers'] = [follower['name'] for follower in task['followers']]
    task['memberships'] = [{
        'project': mb['project']['name'],
        'section': mb['section']['name']
    } for mb in task['memberships']]
    task['tags'] = [tag['name'] for tag in task['tags']]
    task['attachments'] = [{
        'created_at': attachment['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
        'name': attachment['name']
    } for attachment in task['attachments']]

    story_text = ''
    for story in task['stories']:
        story_text += f"Story at: {story['created_at'].strftime('%Y-%m-%d %H:%M:%S')} by {story['created_by']['name'] if story['created_by'] else 'Nobody'}\n{story['text'] if 'text' in story else ''}\n\n"
    summary = llm.chat.completions.create(
        model=llm_model['story_summarize'],
        messages=[{"role": "system", "content": get_prompt_template(PromptTemplate.STORY_SUMMARIZE).format(stories=story_text)}]
    ).choices[0].message.content
    task['stories'] = summary

    return {
        'tasks': [task]
    }

def get_response(state: ReviewState, config: RunnableConfig):
    ## Process context data
    today = datetime.date.today().strftime('%Y-%m-%d')

    client = copy.deepcopy(state['client'])
    client.pop('_id')
    client = json.dumps(client, indent=4)

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
    for task in tasks[max(0, len(tasks) - 25):]:
        if task['completed']:
            completed_tasks.append(task)
        else:
            active_tasks.append(task)
    completed_tasks = json.dumps(completed_tasks, indent=4)
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

def synthesizer(state: ReviewState, config: RunnableConfig):

    return {}

# Conditional Edges
def continue_to_task(state: ReviewState, config: RunnableConfig):
    return [Send('process_task', {'task': task}) for index, task in enumerate(state['raw_tasks'])]


# Setup Graph
def setup_graph():
    graph_builder = StateGraph(ReviewState)

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

    # Stream with config to see full state updates
    config = {"recursion_limit": 100, "configurable": {"thread_id": "test-thread"}}
    for event_part in graph.stream(initial_state, config=config, stream_mode="updates"):
        # event_part is a dictionary where keys are node names and values are their output
        print(f"--- Graph Update ---")
        for node_name, output in event_part.items():
            print(f"Node '{node_name}'")
            # if node_name == "process_task" and "tasks" in output:
            #     print(f"  ^^^ process_task produced tasks, this should trigger accumulator.")
        # To see the full state after each update, you'd need to inspect the graph's internal state
        # or rely on the final event from get_response.

    print("\n--- Final state (from a final invocation if needed, or inspect last event) ---")