import json, copy
from bson import ObjectId
from datetime import datetime

from config import llm_model, get_prompt_template, PromptTemplate
from db import mongo
from src.utils import llm

def mongo_json_serializer(obj):
    """
    Custom JSON serializer for objects not serializable by default json code.
    Specifically handles ObjectId and datetime.datetime.
    """
    if isinstance(obj, ObjectId):
        return str(obj)  # Convert ObjectId to its string representation
    if isinstance(obj, datetime):
        # Convert datetime to ISO 8601 format string.
        # Using isoformat() is standard and includes timezone info if present.
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    # For any other types that json can't handle, it will raise a TypeError
    # You could add more type checks here if needed.
    raise TypeError(f"Type {type(obj)} not serializable")

def func_get_client(client_id, agent: str="review_gen"):
    client = mongo.find_one({"gid": client_id})
    del client["_id"]
    return {"client": client, "clientId": client["gid"]}

def func_get_project(client_id, agent: str="review_gen"):
    project = mongo.find_one({"resource_type": "project", "client": client_id})
    attachments = list(mongo.find({"resource_type": "attachment", "client": client_id, "parent.gid": project["gid"]}))
    project["attachments"] = attachments

    if agent == "review_gen":
        del project["custom_fields"], project["custom_field_settings"]

    del project["_id"], project["gid"], project["color"], project["default_access_level"],\
        project["default_view"], project["minimum_access_level_for_customization"], project["minimum_access_level_for_sharing"], project["permalink_url"], project["privacy_setting"], \
        project["resource_type"], project["workspace"], project["html_notes"], project["created_from_template"], project["from"], project["type"], project["client"]
    project["team"] = project["team"]["name"] if project["team"] else ""
    project["owner"] = project["owner"]["name"] if project["owner"] else ""
    project["followers"] = [follower["name"] for follower in project["followers"]]
    project["members"] = [member["name"] for member in project["members"]]

    return {"project": project}

def func_get_reviews(client_id, agent: str="review_gen"):
    weekly_reviews = list(mongo.find({"type": "weekly", "client": client_id}).sort(["date"]))
    monthly_reviews = list(mongo.find({"type": "monthly", "client": client_id}).sort(["date"]))
    for group in [weekly_reviews, monthly_reviews]:
        for review in group:
            del review["_id"], review["content"], review["client"], review["from"], review["children"], review["parentNoteId"], review["id"]
    return {"weekly": weekly_reviews, "monthly": monthly_reviews}

def func_get_tasks(client_id, agent: str="review_gen"):
    tasks = list(mongo.aggregate([
        {
            "$match": {
                "resource_type": "task",
                "client": client_id,
            }
        }, {
            "$lookup": {
                "from": "mvp",
                "localField": "gid",
                "foreignField": "target.gid",
                "as": "stories",
                "pipeline": [
                    {
                        "$match": {
                            "resource_type": "story"
                        }
                    }, {
                        "$sort": {
                            "created_at": 1
                        }
                    }
                ]
            }
        }, {
            "$lookup": {
                "from": "mvp",
                "localField": "gid",
                "foreignField": "parent.gid",
                "as": "attachments",
                "pipeline": [
                    {
                        "$match": {
                            "resource_type": "attachment"
                        }
                    }
                ]
            }
        }, {
            "$sort": {
                "created_at": 1
            }
        }
    ]))

    for task in tasks:
        del task["_id"]
        for story in task["stories"]:
            del story["_id"]
        for attachment in task["attachments"]:
            del attachment["_id"]

    return {
        "raw_tasks": tasks
    }

def func_process_task(task, agent: str="review_gen"):
    del task["html_notes"], task["hearts"], task["likes"], task["projects"], task["workspace"], task["created_by"], task["client"], task["from"], task["type"]
    task["assignee"] = task["assignee"]["name"] if task["assignee"] else ""
    task["custom_fields"] = [{
        "name": cf["name"],
        "value": cf["display_value"]
    } for cf in task["custom_fields"]]
    task["followers"] = [follower["name"] for follower in task["followers"]]
    task["memberships"] = [{
        "project": mb["project"]["name"],
        "section": mb["section"]["name"]
    } for mb in task["memberships"]]
    task["tags"] = [tag["name"] for tag in task["tags"]]

    if agent == "review_gen":
        task["attachments"] = [{
            "created_at": attachment["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "name": attachment["name"]
        } for attachment in task["attachments"]]

        story_text = ""
        for story in task["stories"]:
            story_text += f'Story at: {story["created_at"].strftime("%Y-%m-%d %H:%M:%S")} by {story["created_by"]["name"] if story["created_by"] else "Nobody"}\n{story["text"] if "text" in story else ""}\n\n'
        summary = llm.chat.completions.create(
            model=llm_model["summarize"],
            messages=[{"role": "system", "content": get_prompt_template(PromptTemplate.STORY_SUMMARIZE).format(stories=story_text)}]
        ).choices[0].message.content
        task["stories"] = summary
    else:
        del task["attachments"], task["stories"]

    return {
        "tasks": [task]
    }

def func_get_response(state, agent: str="review_gen"):
    today = datetime.today().strftime("%Y-%m-%d")

    project = copy.deepcopy(state["project"])
    project["created_at"] = project["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    project["modified_at"] = project["modified_at"].strftime("%Y-%m-%d %H:%M:%S")
    if project["due_on"]:
        project["due_on"] = project["due_on"].strftime("%Y-%m-%d %H:%M:%S")
    if project["due_date"]:
        project["due_date"] = project["due_date"].strftime("%Y-%m-%d %H:%M:%S")

    weekly_reviews = copy.deepcopy(state["weekly"])
    monthly_reviews = copy.deepcopy(state["monthly"])
    for group in [weekly_reviews, monthly_reviews]:
        for review in group:
            review["updatedAt"] = review["updatedAt"].strftime("%Y-%m-%d %H:%M:%S")
            if review["date"] != "":
                review["date"] = review["date"].strftime("%Y-%m-%d")


    tasks = copy.deepcopy(state["tasks"])
    completed_tasks = []
    active_tasks = []
    for task in tasks:
        if task["completed"]:
            completed_tasks.append(task)
        else:
            active_tasks.append(task)
    active_tasks = sorted(active_tasks, key=lambda item: item["due_on"] if item["due_on"] else datetime(3000, 12, 31))
    completed_tasks = sorted(completed_tasks, key=lambda item: item["completed_at"])
    for group in [completed_tasks, active_tasks]:
        for task in group:
            for date in ["created_at", "completed_at", "due_on", "due_date", "modified_at"]:
                if date in task and task[date] is not None:
                    try:
                        task[date] = task[date].strftime("%Y-%m-%d %H:%M:%S")
                    except Exception as e:
                        print(date, task[date])
            try:
                json.dumps(task)
            except:
                print(task)

    return today, project, weekly_reviews, monthly_reviews, completed_tasks, active_tasks
