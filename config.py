from enum import Enum
import os


mongo_info = {
    'url': 'mongodb+srv://johnbrophy1120:Jp2jQQ2p6DcayL1R@cluster0.thosduo.mongodb.net/',
    'database': 'white_marketing',
    'collection': 'mvp',
}

pinecone_info = {
    'index': 'white-marketing',
    'env': 'mvp'
}

llm_model = {
    'review': 'gpt-4o',
    'story_summarize': 'gpt-4.1-nano'
}

class PromptTemplate(Enum):
    REVIEW_GEN = "review_general.md"
    STORY_SUMMARIZE = "story_summarize.md"


def get_prompt_template(prompt_template: PromptTemplate):
    with open(os.path.join('src/prompts', prompt_template.value), "rt", encoding='utf-8') as f:
        return f.read()