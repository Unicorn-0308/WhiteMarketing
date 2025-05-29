import json, os, time, threading, copy
import asana
from asana.rest import ApiException

configuration = asana.Configuration()
configuration.access_token = "2/1210174643501342/1210316415011274:11432dbf64383536966062c64013f318"
api_client = asana.ApiClient(configuration)

lock = threading.Lock()
threads = []
next_t = 30

def load():
    space = {
        # 'updated': ['again'],
        # 'again': [],
    }
    file_names = os.listdir("MVP_data/asana")
    for name in file_names:
        try:
            data = json.load(open(f"MVP_data/asana/{name}", 'r'))
            space[name.split('.json')[0]] = data
        except Exception as e:
            print(name)
    return space

def save(origin_space):
    # with lock:
    space = copy.deepcopy(origin_space)
    for key in space['updated']:
        json.dump(space[key], open(f"MVP_data/asana/{key}.json", 'w'), indent=4)
        print(f"Saved {key}.json")
    space['updated'] = []

def get_response(func, *args, **kwargs):
    while True:
        try:
            return func(*args, **kwargs)
        except ApiException as e:
            if e.status == 429:
                print("Too many requests. Sleeping for 10 seconds.")
            else:
                print(e.status, e)
            time.sleep(10)
        except Exception as e:
            print(e)
            time.sleep(10)

ignore_types = [
    'custom_field_setting',
    'enum_option'
]

opt_fields = {
    'simple': {
        'opt_fields': 'gid,resource_type'
    },
    'team': {
        'opt_fields': 'description,html_description'
    },
    'project': {
        'opt_fields': 'created_from_template,project_brief,html_notes'
    },
    'custom_field': {
        'opt_fields': 'description'
    },
    'task': {
        'opt_fields': 'created_by,dependencies,dependents,html_notes,is_rendered_as_separator,num_subtasks,description'
    },
    'status_update': {
        'opt_fields': 'html_text'
    },
    'story': {
        'opt_fields': 'html_text'
    }
}

api_instant_dict = {
    'workspace': asana.WorkspacesApi(api_client),
    'team': asana.TeamsApi(api_client),
    'user': asana.UsersApi(api_client),
    'team_membership': asana.TeamMembershipsApi(api_client),
    'project': asana.ProjectsApi(api_client),
    'custom_field': asana.CustomFieldsApi(api_client),
    'project_template': asana.ProjectTemplatesApi(api_client),
    'task': asana.TasksApi(api_client),
    'section': asana.SectionsApi(api_client),
    'tag': asana.TagsApi(api_client),
    'status_update': asana.StatusUpdatesApi(api_client),
    'story': asana.StoriesApi(api_client),
    'attachment': asana.AttachmentsApi(api_client),
}

api_get_dict = {
    'workspace': api_instant_dict['workspace'].get_workspace,
    'team': api_instant_dict['team'].get_team,
    'user': api_instant_dict['user'].get_user,
    'team_membership': api_instant_dict['team_membership'].get_team_membership,
    'project': api_instant_dict['project'].get_project,
    'custom_field': api_instant_dict['custom_field'].get_custom_field,
    'project_template': api_instant_dict['project_template'].get_project_template,
    'task': api_instant_dict['task'].get_task,
    'section': api_instant_dict['section'].get_section,
    'tag': api_instant_dict['tag'].get_tag,
    'status_update': api_instant_dict['status_update'].get_status,
    'story': api_instant_dict['story'].get_story,
    'attachment': api_instant_dict['attachment'].get_attachment,
}

def get_data(resource_type, addition:bool = False):
    def get(gid):
        data = get_response(api_get_dict[resource_type], gid, opts={})
        if addition:
            addition_data = get_response(api_get_dict[resource_type], gid, opts=opt_fields[resource_type])
            data.update(addition_data)
        return data
    return get

get_dict = {
    'workspace': get_data('workspace'),
    'team': get_data('team', True),
    'user': get_data('user'),
    'team_membership': get_data('team_membership'),
    'project': get_data('project', True),
    'custom_field': get_data('custom_field', True),
    'project_template': get_data('project_template'),
    'task': get_data('task', True),
    'section': get_data('section'),
    'tag': get_data('tag'),
    'status_update': get_data('status_update', True),
    'story': get_data('story', True),
    'attachment': get_data('attachment'),
}

def expand_data(data, space):
    # try:
    if 'gid' in data and 'resource_type' in data and data['resource_type'] not in ignore_types:
        if data['resource_type'] not in space:
            space[data['resource_type']] = {}
        if data['gid'] not in space[data['resource_type']]:
            data = get_dict[data['resource_type']](data['gid'])
            with lock:
                space[data['resource_type']][data['gid']] = data
            if data['resource_type'] not in space['updated']:
                space['updated'].append(data['resource_type'])
            if data['resource_type'] == 'task':
                print(f"Task Count: {len(space['task'])}")
                if data['num_subtasks']:
                    get_subtasks(data['gid'], space)
            if data['resource_type'] == 'story':
                print(f"Story Count: {len(space['story'])}")
            if data['resource_type'] == 'attachment':
                print(f"Attachment Count: {len(space['attachment'])}")
        else:
            return

    for key in data:
        if isinstance(data[key], dict):
            expand_data(data[key], space)
        elif isinstance(data[key], list):
            for el in data[key]:
                if data['resource_type'] == 'task' \
                    and key == 'custom_fields' \
                    and 'custom_field' in space \
                    and el['gid'] in space['custom_field']:
                    continue
                if isinstance(el, dict):
                    expand_data(el, space)
    # except Exception as e:
    #     print(e, json.dumps(description, indent=4))

def get_workspace(space):
    response = get_response(api_instant_dict['workspace'].get_workspaces, opt_fields['simple'])
    for workspace in response:
        expand_data(workspace, space)

def get_teams(space):
    response = get_response(api_instant_dict['team'].get_teams_for_workspace, '1120263180104321', opt_fields['simple'])
    for team in response:
        expand_data(team, space)

def get_users(space):
    response = get_response(api_instant_dict['user'].get_users_for_workspace, '1120263180104321', opt_fields['simple'])
    for user in response:
        expand_data(user, space)

def get_team_memberships(space):
    users = space['user']
    for user in users:
        response = get_response(api_instant_dict['team_membership'].get_team_memberships_for_user, user, '1120263180104321', opt_fields['simple'])
        for team_membership in response:
            expand_data(team_membership, space)

def get_projects(space):
    response = get_response(api_instant_dict['project'].get_projects_for_workspace, '1120263180104321', opt_fields['simple'])
    for project in response:
        expand_data(project, space)

def get_subtasks(task_gid, space):
    res = get_response(api_instant_dict['task'].get_subtasks_for_task, task_gid, opt_fields['simple'])
    for t in res:
        expand_data(t, space)

def get_tasks(space, project_id):
    global next_t
    projects = space['project']
    projects = list(projects.keys())
    print(projects)
    p_skip = 0
    t_skip = 0
    # for p_index, project in enumerate(MVP_data/asana[p_skip:]):
    p_index = project_id
    project = project_id
    try:
        response = get_response(api_instant_dict['task'].get_tasks_for_project, project_id, opt_fields['simple'])
        response = list(response)
        print(project, len(response))
        if len(response) == 0:
            space['again'].append(project)
        for t_index, task in enumerate(response[t_skip:]):
            expand_data(task, space)
            if (t_skip + t_index + 1) % 500 == 0:
                save(space)
            # print(f"{t_skip + t_index + 1}th(of {len(response)}) Task of {p_skip + p_index + 1}th Project completed.")
            print(f"{t_skip + t_index + 1}th(of {len(response)}) Task of {p_index} Project completed.")
    except ApiException as e:
        print(e, p_index, t_index)
        with lock:
            space['again'].append(project)
    finally:
        save(space)
        with lock:
            if next_t < len(threads):
                threads[next_t].start()
                next_t += 1

def get_status_update(space):
    for project in space['project']:
        response = get_response(api_instant_dict['status_update'].get_statuses_for_object, project, opt_fields['simple'])
        for s in response:
            expand_data(s, space)

story_num = 1000
def get_stories(space, f):
    global story_num
    task_keys = list(space['task'].keys())
    task_keys = task_keys[f : min(f + 31, len(task_keys))]
    for index, task in enumerate(task_keys):
        if task in space['again']:
            continue
        response = get_response(api_instant_dict['story'].get_stories_for_task, task, opt_fields['simple'])
        response = list(response)
        for s in response:
            expand_data(s, space)
        response = get_response(api_instant_dict['attachment'].get_attachments_for_object, task, opt_fields['simple'])
        for a in response:
            expand_data(a, space)
        print(f"{f + index + 1}th Task completed.")
        with lock:
            if len(space['story']) >= story_num:
                print(len(space['story']), story_num)
                save(space)
                story_num += len(space['story']) + 1000

def get_attachments_project(space):
    for project in space['project']:
        response = get_response(api_instant_dict['attachment'].get_attachments_for_object, project, opt_fields['simple'])
        for a in response:
            expand_data(a, space)

client_relateds = [
    "attachment",
    "project",
    "section",
    "story",
    "task"
]
def set_metadata(space):
    for key in space:
        type_ = "client_spec" if key in client_relateds else "general"
        for id_ in space[key]:
            space[key][id_].update({
                'from': "Asana",
                'openAI': [],
                'type': type_,
            })
    for project in space['project']:
        if space['project'][project]["name"][:3].isnumeric():
            space['project'][project]["openAI"] = [space['project'][project]["name"][:3]]
    for task in space['task']:
        for project in space['task'][task]['projects']:
            space['task'][task]['openAI'].extend(space['project'][project["gid"]]["openAI"])
        if space['task'][task]['parent']:
            space['task'][task]['openAI'].extend(space['task'][space['task'][task]['parent']["gid"]]["openAI"])
    for attachment in space['attachment']:
        space['attachment'][attachment]["openAI"] = space[space['attachment'][attachment]["parent"]["resource_type"]][space['attachment'][attachment]["parent"]["gid"]]["openAI"]
    for section in space['section']:
        space['section'][section]["openAI"] = space['project'][space['section'][section]["project"]["gid"]]["openAI"]
    for story in space['story']:
        space['story'][story]["openAI"] = space[space['story'][story]["target"]["resource_type"]][space['story'][story]["target"]["gid"]]["openAI"]
    space["updated"] = list(space.keys())


if __name__ == "__main__":
    space = load()

    # get_workspace(space)
    # get_teams(space)
    # get_users(space)
    # get_team_memberships(space)
    # get_projects(space)
    # num = len(space['again'])
    # for i in ["1205094445372673", "1208244723112788", "1210007150417601"]:
    #     threads.append(threading.Thread(target=get_tasks, args=(space, i), daemon=True))
    #     threads[-1].start()
    # space['again'] = space['again'][num:]
    #
    # for t in threads:
    #     t.join()
    # get_status_update(space)
    # for i in range(10):
    #     threads.append(threading.Thread(target=get_stories, args=(space, 31 * i), daemon=True))
    #     threads[i].start()
    #
    # for t in threads:
    #     t.join()
    # get_attachments_project(space)

    # set_metadata(space)
    save(space)