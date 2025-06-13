from enum import Enum
import os


mongo_info = {
    'url': 'mongodb+srv://White-Market:Jp2jQQ2p6DcayL1R@cluster0.kae45en.mongodb.net/',
    'database': 'white_marketing',
    'collection': 'data',
}

pinecone_info = {
    'index': 'white-marketing',
    'env': 'data'
}

llm_model = {
    'review': 'gpt-4o',
    'task': 'gpt-4o',
    'summarize': 'gpt-4.1-nano',
    'query': 'gpt-4o',
    'general': 'gpt-4o',
    'embedding': 'text-embedding-3-small',
}

class PromptTemplate(Enum):
    REVIEW_GEN = "review_generation.md"
    STORY_SUMMARIZE = "story_summarize.md"
    TASK_INFO_GEN = "task_generation_info.md"
    TASK_GEN = "task_generation_instance.md"
    CLIENT_SUMMARIZE = "client_summarize.md"
    GENERAL_RESPONSE = "general_response.md"
    TOOL_GEN = "tool_generation.md"


def get_prompt_template(prompt_template: PromptTemplate):
    with open(os.path.join('src/prompts', prompt_template.value), "rt", encoding='utf-8') as f:
        return f.read()