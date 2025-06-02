import copy, json
import datetime
# from dotenv import load_dotenv
# load_dotenv('./../../.env')

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, HumanMessage
from db import mongo, pinecone

from config import PromptTemplate, get_prompt_template, llm_model, pinecone_info
from src.agents.utils import func_get_client, func_get_project, func_get_reviews, func_get_tasks, \
    func_process_task, func_get_response
from src.models.general import GeneralState, TaskState, ToolState
from src.utils import llm


# Nodes
def get_client(state: GeneralState, config: RunnableConfig):
    client = func_get_client(state['clientId'], agent="task_gen")
    data = list(mongo.find({ 'type': "client_spec", 'client': "009", 'from': "Slite", 'content': {'$ne': ""} }))
    client_spec = ''
    for note in data:
        client_spec += f"# {note['title']}\n{json.dumps(note['content'], indent=4)}\n\n"

    summary = llm.chat.completions.create(
        model=llm_model['summarize'],
        messages=[{"role": "system", "content": get_prompt_template(PromptTemplate.CLIENT_SUMMARIZE).format(client=json.dumps(client['client'], indent=4), client_spec=client_spec.strip())}]
    ).choices[0].message.content

    return { 'clientId': client['clientId'], 'client_spec': summary }

def get_project(state: GeneralState, config: RunnableConfig):
    return func_get_project(state['clientId'], agent="task_gen")

def get_reviews(state: GeneralState, config: RunnableConfig):
    return func_get_reviews(state['clientId'], agent="task_gen")

def get_tasks(state: GeneralState, config: RunnableConfig):
    return func_get_tasks(state['clientId'], agent="task_gen")

def process_task(state: TaskState, config: RunnableConfig):
    return func_process_task(state['task'], agent="task_gen")

def synthesizer(state: GeneralState, config: RunnableConfig):
    return {}

def get_tools(state: GeneralState, config: RunnableConfig):
    ## Process context data
    today, project, weekly_reviews, monthly_reviews, completed_tasks, active_tasks = func_get_response(state, "general")

    project = json.dumps(project, indent=4)

    weekly = ''
    for review in weekly_reviews[max(0, len(weekly_reviews) - 5):]:
        weekly += f"Weekly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"
    monthly = ''
    for review in monthly_reviews[max(0, len(weekly_reviews) - 5):]:
        monthly += f"Monthly Review on {review['date']}\n{json.dumps(review, indent=4)}\n"

    completed_tasks = json.dumps(completed_tasks[max(0, len(weekly_reviews) - 100):], indent=4)
    active_tasks = json.dumps(active_tasks, indent=4)

    prompt = get_prompt_template(PromptTemplate.TOOL_GEN)
    prompt = prompt\
        .replace('{{0}}', today)\
        .replace('{{1}}', state['client_spec'])\
        .replace('{{2}}', project)\
        .replace('{{3}}', weekly)\
        .replace('{{4}}', monthly)\
        .replace('{{5}}', completed_tasks)\
        .replace('{{6}}', active_tasks)
    
    result = llm.responses.create(
        model=llm_model["query"],
        input=[{
            'role': 'system',
            'content': prompt,
        }] + [{
            'role': 'user' if isinstance(message, HumanMessage) else 'assistant',
            'content': message.content
        } for message in state['messages']],
        tools=[{
            "type": "function",
            "name": "mongo_filter",
            "description": "MongoDB Filter, Sort and Limit. Use this tool to get exact small amount data with much conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "This is the reason for why you decide to use this tool. It will be used in response. This is not empty."
                    },
                    "filter": {
                        "type": "object",
                        "description": "This is mongoDB filter object for python"
                    },
                    "sort": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {
                                        "type": "string",
                                    },
                                    {
                                        "type": "number",
                                        "enum": [-1, 1]
                                    }
                                ]
                            }
                        },
                        "description": "This is mongoDB sort object for python, not empty."
                    },
                    "limit": {
                        "type": "number",
                        "description": "This is mongoDB limit object for python, not negative."
                    }
                },
                "required": [
                    "purpose",
                    "filter",
                    "sort",
                    "limit"
                ],
                "additionalProperties": False
            }
        }, {
            "type": "function",
            "name": "mongo_aggregation",
            "description": "MongoDB Aggregation. Use this tool for global data collecting such as counting, grouping and so on. Prefer this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "This is the reason for why you decide to use this tool. It will be used in response. This is not empty."
                    },
                    "pipeline": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "description": "This is mongoDB aggregation stage object for python"
                        },
                        "description": "This is mongoDB filter object for python"
                    }
                },
                "required": [
                    "purpose",
                    "pipeline",
                ],
                "additionalProperties": False
            }
        }, {
            "type": "function",
            "name": "pinecone_search",
            "description": "Pinecone vector search, meta filter and top k. use this tool for semantic search, that is difficult for mongo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {
                        "type": "string",
                        "description": "This is the reason for why you decide to use this tool. It will be used in response. This is not empty."
                    },
                    "query": {
                        "type": "string",
                        "description": "This is query string for vector search"
                    },
                    "top_k": {
                        "type": "number",
                        "description": "This is top k for vector search"
                    },
                    "meta_filter": {
                        "type": "object",
                        "description": "This is meta filter for vector search."
                    }
                },
                "required": [
                    "purpose",
                    "query",
                    "top_k",
                    "meta_filter"
                ],
                "additionalProperties": False
            }
        }]
    ).output

    return {'tools': [{
        'tool': tool.name,
        'param': json.loads(tool.arguments)
    } for tool in result]}

def mongo_filter(state: ToolState):
    tool = state['tool']

    result = mongo.find(tool["filter"])
    if len(tool["sort"]):
        result = result.sort(tool["sort"])
    result = result.limit(tool["limit"])
    result = list(result)
    for el in result:
        if 'from' in el and el['from'] == 'Slite' and 'sections' in el:
            del el['sections']

    return {
        'datas': [{
            'purpose': tool["purpose"],
            'result': list(result)
        }]
    }

def mongo_aggregation(state: ToolState):
    tool = state['tool']

    result = mongo.aggregate(tool["pipeline"])

    return {
        'datas': [{
            'purpose': tool["purpose"],
            'result': list(result)
        }]
    }

def pinecone_search(state: ToolState):
    tool = state['tool']

    embedding = llm.embeddings.create(
        input=tool["query"],
        model=llm_model['embedding'],
    ).data[0].embedding
    try:
        results = pinecone.query(
            vector=embedding,
            filter=tool["meta_filter"],
            top_k=tool["top_k"],
            include_metadata=True,
            namespace=pinecone_info['env']
        )
    except Exception as e:
        del tool["meta_filter"]['client']
        results = pinecone.query(
            vector=embedding,
            filter=tool["meta_filter"],
            top_k=tool["top_k"],
            include_metadata=True,
            namespace=pinecone_info['env']
        )
    data = results.get("matches", [])
    results = {}
    for el in data:
        if el['metadata']['from'] == 'Slite' and el['metadata']['id'] not in results:
            document = mongo.find_one({'id': el['metadata']['id']})
            del document['_id'], document['sections']
        elif el['metadata']['from'] == 'Asana' and el['metadata']['id'] not in results:
            document = mongo.find_one({'gid': el['metadata']['id']})
            del document['_id']
        else:
            continue

        for date in ["created_at", "completed_at", "due_on", "due_date", "modified_at", "updated_at", "date", "updatedAt"]:
            if date in document and document[date]:
                try:
                    document[date] = document[date].strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    print(date, document[date])
        results[el['metadata']['id']] = document

    return {
        'datas': [{
            'purpose': tool["purpose"],
            'result': results
        }]
    }

def get_response(state: GeneralState, config: RunnableConfig):
    today = datetime.date.today().strftime('%Y-%m-%d')

    project = copy.deepcopy(state['project'])
    project['created_at'] = project['created_at'].strftime("%Y-%m-%d %H:%M:%S")
    project['modified_at'] = project['modified_at'].strftime("%Y-%m-%d %H:%M:%S")
    if project['due_on']:
        project['due_on'] = project['due_on'].strftime("%Y-%m-%d %H:%M:%S")
    if project['due_date']:
        project['due_date'] = project['due_date'].strftime("%Y-%m-%d %H:%M:%S")

    prompt = get_prompt_template(PromptTemplate.GENERAL_RESPONSE)
    prompt = prompt.format(
        today=today,
        client_spec=state['client_spec'],
        project_data=project,
        datas=json.dumps(state['datas'], indent=4),
    )

    writer = get_stream_writer()
    stream = llm.responses.create(
        model=llm_model["general"],
        input=[{
            'role': 'system',
            'content': prompt,
        }] + [{
            'role': 'user' if isinstance(message, HumanMessage) else 'assistant',
            'content': message.content
        } for message in state['messages']],
        stream=True,
    )
    final_text = ''
    for event in stream:
        if event.type == 'response.output_text.delta':
            final_text += event.delta
            writer({'delta': event.delta})
    return {
        'messages': [AIMessage(content=final_text)],
    }


# Conditional Edges
def continue_to_task(state: GeneralState, config: RunnableConfig):
    return [Send('process_task', {'task': task}) for index, task in enumerate(state['raw_tasks'])]

def continue_to_tool(state: GeneralState, config: RunnableConfig):
    return [Send(tool["tool"], {'tool': tool["param"]}) for index, tool in enumerate(state['tools'])]


# Setup Graph
def setup_graph():
    graph_builder = StateGraph(GeneralState)

    graph_builder.add_node(get_client)
    graph_builder.add_node(get_project)
    graph_builder.add_node(get_reviews)
    graph_builder.add_node(get_tasks)
    graph_builder.add_node(process_task)
    graph_builder.add_node(synthesizer)
    graph_builder.add_node(get_tools)
    graph_builder.add_node(mongo_filter)
    graph_builder.add_node(mongo_aggregation)
    graph_builder.add_node(pinecone_search)
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
    graph_builder.add_edge('process_task', 'get_tools')
    graph_builder.add_conditional_edges('get_tools', continue_to_tool, ["mongo_filter", "mongo_aggregation", "pinecone_search"])
    graph_builder.add_edge('mongo_filter', 'get_response')
    graph_builder.add_edge('mongo_aggregation', 'get_response')
    graph_builder.add_edge('pinecone_search', 'get_response')
    
    graph_builder.add_edge('get_response', END)

    return graph_builder


if __name__ == '__main__':
    try:
        graph = setup_graph().compile()  # graph is compiled in setup_graph now
        code = graph.get_graph().draw_mermaid()

        initial_state = {
            "clientId": "009",
            "messages": [HumanMessage(content="How should I create new weekly review for client 009?")]
        }

        # Stream with configuration to see full state updates
        configuration = {"recursion_limit": 100, "configurable": {"thread_id": "test-thread"}}
        for chunk in graph.stream(initial_state, config=configuration, stream_mode="custom"):
            print(chunk['delta'], end='')
    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()