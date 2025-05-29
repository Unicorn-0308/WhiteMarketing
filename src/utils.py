import os
from openai import OpenAI

llm = OpenAI(api_key=os.environ["OPENAI_API_KEY"])