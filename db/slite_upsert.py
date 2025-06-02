import datetime
import json, sys, threading
from pinecone import Pinecone, ServerlessSpec
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from openai import OpenAI
import certifi

index_name = "white-marketing"
env = "mvp"
dbname = "white_marketing"
collection_name = "mvp"

ai_client = OpenAI()

def upsert(notes, note_ids, indexModel, collection):
    inputs = []
    for note_id in note_ids:
        for section in notes[note_id]["sections"]:
            inputs.append(notes[note_id]["sections"][section])

    response = ai_client.embeddings.create(
        model='text-embedding-3-small',
        input=inputs
    ).data

    records = []
    index = 0
    for note_id in note_ids:
        for section in notes[note_id]["sections"]:
            print(f"{note_id}-{section}".lower())
            records.append({
                'id': f"{note_id}-{index}".lower(),
                'values': response[index].embedding,
                'metadata': {
                    'from': notes[note_id]['from'],
                    'client': notes[note_id]['client'],
                    'type': notes[note_id]['type'],
                    'date': notes[note_id]['date'] if notes[note_id]['date'] else '',
                    'id': notes[note_id]['id'],
                    'section': section,
                }
            })
            index += 1

        notes[note_id]['updatedAt'] = datetime.datetime.fromisoformat(notes[note_id]['updatedAt'])
        if notes[note_id]['date']:
            notes[note_id]['date'] = datetime.datetime.fromisoformat(notes[note_id]['date'])
        collection.update_one({"id": notes[note_id]["id"]}, {"$set": notes[note_id]}, upsert=True)

    indexModel.upsert(records, namespace=env)




if __name__ == "__main__":
    pc = Pinecone(api_key='pcsk_6QLqUr_7neqLCLusw49wn3FRNKoWgsN15C3aTxj5sCLL13VQJLYCg4fBdfUCAPfFPe6P1m')
    if not pc.has_index(index_name):
        indexModel = pc.create_index(
            name=index_name,
            vector_type="dense",
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1",
            ),
            deletion_protection="disabled",
            tags={
                "environment": env,
            }
        )
    else:
        indexModel = pc.Index(index_name)

    try:
        client = MongoClient('mongodb+srv://johnbrophy1120:Jp2jQQ2p6DcayL1R@cluster0.thosduo.mongodb.net/', tlsCAFile=certifi.where())
        client.admin.command('ismaster')
        print("MongoDB connection successful!")
        collection = client[dbname][collection_name]
    except ConnectionFailure:
        print("MongoDB connection failed!")
        sys.exit(1)

    notes = json.load(open("MVP_data/slite.json", "r"))
    ids = list(notes.keys())
    threads = []
    for i in range(7):
        threads.append(threading.Thread(target=upsert, args=(notes, ids[i * 40 : min(i * 40 + 40, len(ids))], indexModel, collection)))
        threads[-1].start()
    for thread in threads:
        thread.join()


