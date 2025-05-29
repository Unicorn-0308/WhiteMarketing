import sys, os
import certifi
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from pinecone import Pinecone, ServerlessSpec

from src.config import mongo_info, pinecone_info


try:
    client = MongoClient(mongo_info["url"], tlsCAFile=certifi.where())
    client.admin.command('ismaster')
    print("MongoDB connection successful!")
    mongo = client[mongo_info["database"]][mongo_info["collection"]]
except ConnectionFailure:
    print("MongoDB connection failed!")
    sys.exit(1)

pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
if not pc.has_index(pinecone_info["index"]):
    pinecone = pc.create_index(
        name=pinecone_info["index"],
        vector_type="dense",
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        ),
        deletion_protection="disabled",
        tags={
            "environment": pinecone_info["env"],
        }
    )
else:
    pinecone = pc.Index(pinecone_info["index"])