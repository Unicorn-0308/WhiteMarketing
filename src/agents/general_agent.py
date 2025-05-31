import copy, json
import datetime
from dotenv import load_dotenv
load_dotenv('.env')

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, HumanMessage
from db import mongo, pinecone

from config import PromptTemplate, get_prompt_template, llm_model, pinecone_info
from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, \
    func_process_task, func_get_response
from src.models.general import GeneralState, TaskState, Tools, ToolState, MongoFilter, MongoAggregation, PineconeQuery
from src.utils import llm


# Nodes
def get_client(state: GeneralState, config: RunnableConfig):
    client = func_get_client(state['clientId'], agent="task_gen")
    data = list(mongo.find({ 'type': "client_spec", 'client': "009", 'from': "Slite", 'content': {'$ne': ""} }))
    client_spec = ''
    for note in data:
        client_spec += f"# {note['title']}\n{note['content']}\n\n"

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
    prompt = prompt.format(
        today=today,
        client_spec=state['client_spec'],
        project_data=project,
        weekly_reviews=weekly,
        monthly_reviews=monthly,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks,
    )
    
    tools = llm.responses.parse(
        model=llm_model["query"],
        input=[{
            'role': 'developer',
            'content': prompt,
        }, {
            'role': 'user',
            'content': state['messages'][-1].content
        }],
        text_format=Tools
    ).output_parsed

    return {'tools': tools}

def mongo_filter(state: ToolState):
    tool = state['tool']
    if not isinstance(tool, MongoFilter):
        return {}

    result = mongo.collection.find(tool.filter)
    if len(tool.sort):
        result = result.sort(tool.sort)
    result = result.limit(tool.limit)
    result = list(result)
    for el in result:
        if 'from' in el and el['from'] == 'Slite' and 'sections' in el:
            del el['sections']

    return {
        'datas': [{
            'purpose': state['purpose'],
            'result': list(result)
        }]
    }

def mongo_aggregation(state: ToolState):
    tool = state['tool']
    if not isinstance(tool, MongoAggregation):
        return {}

    result = mongo.collection.aggregate(tool.pipeline)

    return {
        'datas': [{
            'purpose': state['purpose'],
            'result': list(result)
        }]
    }

def pinecone_search(state: ToolState):
    tool = state['tool']
    if not isinstance(tool, PineconeQuery):
        return {}

    embedding = llm.embeddings.create(
        input=tool.query,
        model=llm_model['embedding'],
    ).data[0].embedding
    results = pinecone.indexModel.query(
        vector=embedding,
        filter=tool.meta_filter,
        top_k=tool.top_k,
        include_metadata=True,
        namespace=pinecone_info['env']
    )

    return {
        'datas': [{
            'purpose': state['purpose'],
            'result': results.get("matches", [])
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
            'role': 'developer',
            'content': prompt,
        }],
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
    return [Send(tool.tool, {'tool': tool.param, 'purpose': tool.purpose}) for index, tool in enumerate(state['tools'])]


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
            "messages": [HumanMessage(content="How many tasks are belong to user?")]
        }

        # Stream with configuration to see full state updates
        configuration = {"recursion_limit": 100, "configurable": {"thread_id": "test-thread"}}
        for chunk in graph.stream(initial_state, config=configuration, stream_mode="custom"):
            print(chunk['delta'], end='')
    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()