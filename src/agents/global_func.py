from typing import Any

from langchain_core.runnables import RunnableConfig

from config import llm_model, get_prompt_template, PromptTemplate
from db import mongo
from src.utils import llm


def func_get_client(client_id, agent: str="review_gen"):
    client = mongo.find_one({"gid": client_id})
    del client['_id']
    return {'client': client, 'clientId': client['gid']}

def func_get_project(client_id, agent: str="review_gen"):
    project = mongo.find_one({"resource_type": 'project', "client": client_id})
    attachments = list(mongo.find({"resource_type": 'attachment', "client": client_id, "parent.gid": project['gid']}))
    project['attachments'] = attachments

    if agent == "review_gen":
        del project['custom_fields'], project['custom_field_settings']

    del project['_id'], project['gid'], project['color'], project['default_access_level'],\
        project['default_view'], project['minimum_access_level_for_customization'], project['minimum_access_level_for_sharing'], project['permalink_url'], project['privacy_setting'], \
        project['resource_type'], project['workspace'], project['html_notes'], project['created_from_template'], project['from'], project['type'], project['client']
    project['team'] = project['team']['name'] if project['team'] else ''
    project['owner'] = project['owner']['name'] if project['owner'] else ''
    project['followers'] = [follower['name'] for follower in project['followers']]
    project['members'] = [member['name'] for member in project['members']]

    return {'project': project}

def func_get_reviews(client_id, agent: str="review_gen"):
    weekly_reviews = list(mongo.find({'type': 'weekly', "client": client_id}).sort(['date']))
    monthly_reviews = list(mongo.find({'type': 'monthly', "client": client_id}).sort(['date']))
    for group in [weekly_reviews, monthly_reviews]:
        for review in group:
            del review['_id'], review['sections'], review['client'], review['from'], review['children'], review['parentNoteId'], review['id']
    return {'weekly': weekly_reviews, 'monthly': monthly_reviews}

def func_get_tasks(client_id, agent: str="review_gen"):
    tasks = list(mongo.aggregate([
        {
            '$match': {
                'resource_type': 'task',
                'client': client_id,
            }
        }, {
            '$lookup': {
                'from': 'mvp',
                'localField': 'gid',
                'foreignField': 'target.gid',
                'as': 'stories',
                'pipeline': [
                    {
                        '$match': {
                            'resource_type': 'story'
                        }
                    }, {
                        '$sort': {
                            'created_at': 1
                        }
                    }
                ]
            }
        }, {
            '$lookup': {
                'from': 'mvp',
                'localField': 'gid',
                'foreignField': 'parent.gid',
                'as': 'attachments',
                'pipeline': [
                    {
                        '$match': {
                            'resource_type': 'attachment'
                        }
                    }
                ]
            }
        }, {
            '$sort': {
                'created_at': 1
            }
        }
    ]))

    return {
        'raw_tasks': tasks
    }

def func_process_task(task, agent: str="review_gen"):
    del task['_id'], task['html_notes'], task['hearts'], task['likes'], task['projects'], task['workspace'], task['created_by'], task['client'], task['from'], task['type']
    task['assignee'] = task['assignee']['name'] if task['assignee'] else ''
    task['custom_fields'] = [{
        'name': cf['name'],
        'value': cf['display_value']
    } for cf in task['custom_fields']]
    task['followers'] = [follower['name'] for follower in task['followers']]
    task['memberships'] = [{
        'project': mb['project']['name'],
        'section': mb['section']['name']
    } for mb in task['memberships']]
    task['tags'] = [tag['name'] for tag in task['tags']]

    if agent == 'review_gen':
        task['attachments'] = [{
            'created_at': attachment['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'name': attachment['name']
        } for attachment in task['attachments']]

        story_text = ''
        for story in task['stories']:
            story_text += f"Story at: {story['created_at'].strftime('%Y-%m-%d %H:%M:%S')} by {story['created_by']['name'] if story['created_by'] else 'Nobody'}\n{story['text'] if 'text' in story else ''}\n\n"
        summary = llm.chat.completions.create(
            model=llm_model['story_summarize'],
            messages=[{"role": "system", "content": get_prompt_template(PromptTemplate.STORY_SUMMARIZE).format(stories=story_text)}]
        ).choices[0].message.content
        task['stories'] = summary
    else:
        del task['attachments'], task['stories']

    return {
        'tasks': [task]
    }