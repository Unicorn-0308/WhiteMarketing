import datetime
import json, sys, threading, csv
from pinecone import Pinecone, ServerlessSpec
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from openai import OpenAI
import certifi

from asana_template import func_dict

index_name = "white-marketing"
env = "mvp"
dbname = "white_marketing"
collection_name = "mvp"

ai_client = OpenAI()

def upsert_pinecone(space: dict, indexModel):
    records = []
    inputs = []
    for resource_type in [
        # "attachment",
        # "project",
        # "section",
        "story",
        # "task"
    ]:
        for key, data in space[resource_type].items():
            records.append({
                "id": key,
                "metadata": {
                    "from": data["from"],
                    "client": data["client"],
                    "type": data["type"],
                    "id": data["gid"],
                    "resource_type": resource_type,
                }
            })
            text = func_dict[resource_type](data)
            inputs.append(text)
    response = ai_client.embeddings.create(
        model='text-embedding-3-small',
        input=inputs[:2048]
    ).data
    response.extend(ai_client.embeddings.create(
        model='text-embedding-3-small',
        input=inputs[2048:]
    ).data)

    for index, record in enumerate(records):
        record["values"] = response[index].embedding

    for index, record in enumerate(records):
        indexModel.upsert([record], namespace=env)
        print(index, len(records))

def upsert_mongo(space: dict, collection):
    for resource_type, data in space.items():
        for key, item in data.items():
            for date in ["created_at", "completed_at", "due_on", "due_date", "modified_at"]:
                if date in item and item[date] is not None:
                    item[date] = datetime.datetime.fromisoformat(item[date])
        collection.insert_many(data.values())
        print(resource_type)


if __name__ == "__main__":
    # pc = Pinecone(api_key='pcsk_6QLqUr_7neqLCLusw49wn3FRNKoWgsN15C3aTxj5sCLL13VQJLYCg4fBdfUCAPfFPe6P1m')
    # if not pc.has_index(index_name):
    #     indexModel = pc.create_index(
    #         name=index_name,
    #         vector_type="dense",
    #         dimension=1536,
    #         metric="cosine",
    #         spec=ServerlessSpec(
    #             cloud="aws",
    #             region="us-east-1",
    #         ),
    #         deletion_protection="disabled",
    #         tags={
    #             "environment": env,
    #         }
    #     )
    # else:
    #     indexModel = pc.Index(index_name)

    # try:
    #     client = MongoClient('mongodb+srv://johnbrophy1120:Jp2jQQ2p6DcayL1R@cluster0.thosduo.mongodb.net/', tlsCAFile=certifi.where())
    #     client.admin.command('ismaster')
    #     print("MongoDB connection successful!")
    #     collection = client[dbname][collection_name]
    # except ConnectionFailure:
    #     print("MongoDB connection failed!")
    #     sys.exit(1)

    space = json.load(open("MVP_data/asana.json", "r"))
    # upsert_pinecone(space, indexModel)
    # upsert_mongo(space, collection)
