import copy, json
import datetime
from dotenv import load_dotenv
from llama_index.core.indices.vector_store.retrievers.auto_retriever.prompts import example_query

load_dotenv('./../../.env')

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.config import get_stream_writer
from langchain_core.messages import AIMessage, HumanMessage
from db import mongo, pinecone

from config import PromptTemplate, get_prompt_template, llm_model, pinecone_info
from src.agents.global_func import func_get_client, func_get_project, func_get_reviews, func_get_tasks, \
    func_process_task, func_get_response
from src.models.general import GeneralState, TaskState, Tools, Tools_, ToolState, MongoFilter, MongoAggregation, PineconeQuery, Tool
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
    example_prompt = get_prompt_template(PromptTemplate.EXAMPLES)
    prompt = prompt.format(
        today=today,
        example=example_prompt,
        client_spec=f"User ID: {str(state['clientId'])}\n{state['client_spec']}",
        project_data=project,
        weekly_reviews=weekly,
        monthly_reviews=monthly,
        completed_tasks=completed_tasks,
        active_tasks=active_tasks,
    )
    
    # Use a simpler approach - get the response as text and parse it manually
    response = llm.chat.completions.create(
        model=llm_model["query"],
        messages=[{
            'role': 'developer',
            'content': prompt + "\n\nPlease respond with a JSON object in the following format:\n" + json.dumps({
                "tools": [
                    {
                        "tool": "mongo_filter | mongo_aggregation | pinecone_search",
                        "param": {
                            "purpose": "description of what this tool is for",
                            "filter": {"field": "value"},  # for mongo_filter
                            "sort": [{"field": 1}],  # for mongo_filter
                            "limit": 10,  # for mongo_filter
                            "pipeline": [{"$match": {}}],  # for mongo_aggregation
                            "query": "search query",  # for pinecone_search
                            "top_k": 10,  # for pinecone_search
                            "meta_filter": {}  # for pinecone_search
                        }
                    }
                ]
            }, indent=2)
        }, {
            'role': 'user',
            'content': state['messages'][-1].content
        }]
    )
    
    # Parse the response
    try:
        tools_data = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract JSON from the response
        content = response.choices[0].message.content
        # Find JSON content between ```json and ```
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            tools_data = json.loads(json_match.group(1))
        else:
            # Try to find any JSON object in the response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                tools_data = json.loads(json_match.group(0))
            else:
                tools_data = {"tools": []}
    
    # Convert the response to the expected format
    tools = []
    for tool_data in tools_data.get('tools', []):
        tool_name = tool_data['tool']
        param = tool_data['param']
        
        if tool_name == 'mongo_filter':
            tool_obj = Tool(
                tool=tool_name,
                param=MongoFilter(
                    purpose=param['purpose'],
                    filter=param.get('filter', {}),
                    sort=param.get('sort', []),
                    limit=param.get('limit', 10)
                )
            )
        elif tool_name == 'mongo_aggregation':
            tool_obj = Tool(
                tool=tool_name,
                param=MongoAggregation(
                    purpose=param['purpose'],
                    pipeline=param.get('pipeline', [])
                )
            )
        elif tool_name == 'pinecone_search':
            tool_obj = Tool(
                tool=tool_name,
                param=PineconeQuery(
                    purpose=param['purpose'],
                    query=param.get('query', ''),
                    top_k=param.get('top_k', 10),
                    meta_filter=param.get('meta_filter')
                )
            )
        tools.append(tool_obj)
    
    return {'tools': Tools(tools=tools)}

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
            'purpose': tool.purpose,
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
            'purpose': tool.purpose,
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
            'purpose': tool.purpose,
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
        }, {
            'role': 'user',
            'content': state['messages'][-1].content
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
    return [Send(tool.tool, {'tool': tool.param}) for index, tool in enumerate(state['tools'].tools)]


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
            "messages": [HumanMessage(content="How many active tasks are belong to user?")]
        }

        # Stream with configuration to see full state updates
        configuration = {"recursion_limit": 100, "configurable": {"thread_id": "test-thread"}}
        for chunk in graph.stream(initial_state, config=configuration, stream_mode="custom"):
            print(chunk['delta'], end='')
    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()