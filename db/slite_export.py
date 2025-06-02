import asyncio
import os

import nest_asyncio
import requests, json, time, re, datetime
from threading import Thread

from attr import attributes

from slite_template import split_markdown_into_sections, split_markdown_by_horizontal_rule


ids = ["LxAP8PpKzOlG66", "6Kf80yv9CxLy70", "O8zROw_8JyQH_O"]

def get_response(url, headers, name, interval=60):
    response = requests.get(url, headers=headers)
    while response.status_code == 429 or response.status_code == 503:
        print(name, url, response.status_code, response.text)
        time.sleep(10)
        response = requests.get(url, headers=headers)
    return response

async def get_doc(doc_gid: str, headers, client=[], type_="general"):
    result = {}
    response = None
    try:
        response = get_response(f"https://api.slite.com/v1/notes/{doc_gid}", headers=headers, name="doc")
        if response.status_code != 200:
            print("Error", response)
            return result
        doc_self = response.json()

        if type_ == "weekly" or type_ == "monthly":
            date = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", doc_self['title'])
            if len(date) > 0:
                if doc_self['parentNoteId'] == 'ow9OJ5mJo6YtFq':
                    date = datetime.datetime.strptime(date[0], "%d/%m/%Y").date().strftime('%Y-%m-%d')
                else:
                    date = datetime.datetime.strptime(date[0], "%m/%d/%Y").date().strftime('%Y-%m-%d')
            else:
                date = ''
        else:
            date = ''
        doc_self.update({
            "sections": await split_markdown_into_sections(doc_self['content'], heading_level=3),
            "from": "Slite",
            "client": client,
            "type": type_,
            "date": date,
        })
        # doc_self['sections_by_hr'] = split_markdown_by_horizontal_rule(doc_self['content'])
        result[doc_self["id"]] = doc_self
        result[doc_self["id"]]["children"] = []

        cursor = ""
        while True:
            response = get_response(f"https://api.slite.com/v1/notes/{doc_gid}/children?cursor={cursor}", headers=headers, name="doc_children")
            children = response.json()
            for child in children["notes"]:
                result[doc_self["id"]]["children"].append(child["id"])
                if doc_self["title"] == "Clients" and child["title"][:3].isnumeric():
                    if child['id'] not in ids:
                        continue
                    res = await get_doc(child["id"], headers, client=[child["title"][:3]], type_="client_spec")

                elif doc_self["title"] == "Weekly Reviews" and len(doc_self["client"]):
                    res = await get_doc(child["id"], headers, client=doc_self["client"], type_="weekly")

                elif doc_self["title"] == "Monthly Reviews" and len(doc_self["client"]):
                    res = await get_doc(child["id"], headers, client=doc_self["client"], type_="monthly")

                else:
                    res = await get_doc(child["id"], headers, client=client, type_=type_)
                result.update(res)

            if not children["hasNextPage"]:
                break

            cursor = children["nextCursor"]
        print(doc_self["id"], doc_self["title"], "Completed")

    except Exception as e:
        print(doc_gid, e, response.text)
    return result

def get_extra(notes, headers):
    num_extra = 0

    page = 0
    try:
        while True:
            response = get_response(f"https://api.slite.com/v1/search-notes?&page={page}", headers=headers, name="extra")
            data = response.json()

            for el in data["hits"]:
                if el["title"] == "My private channel":
                    continue

                if el["id"] not in notes:
                    res = get_doc(el["id"], headers)
                    notes.update(res)
                    if len(res.keys()) > 1:
                        num_extra += 1
                    print(f"Extra doc {el['id']}")

            if page == data["nbPages"] - 1:
                break

            page += 1
    except Exception as e:
        print(page, e)

    return notes, num_extra

def get_data(token):
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token}"
    }

    num_channel = 1

    notes = {}

    page = 0
    try:
        while True:
            response = get_response(f"https://api.slite.com/v1/search-notes?depth=0&page={page}", headers=headers, name="description")
            data = response.json()

            for el in data["hits"]:
                if el["title"] == "My private channel":
                    continue

                channel = get_doc(el["id"], headers)
                notes.update(channel)

                print(f"Channel {el['title']}, Total: {num_channel}")
                num_channel += 1

            if page == data["nbPages"] - 1:
                break

            page += 1
    except Exception as e:
        print(page, e)

    notes, num_ex = get_extra(notes, headers)
    while num_ex:
        notes, num_ex = get_extra(notes, headers)

    return notes

def thread_get(api_token, id_):
    result = asyncio.run(get_doc(id_, {
        "accept": "application/json",
        "authorization": f"Bearer {api_token}"
    }))

    with open(f"MVP_data/{id_}_Slite.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4)

if __name__ == "__main__":
    nest_asyncio.apply()
    # api_token = "5L173-matkwjZ7x3asV_-e58b6b8c1fdb3db3aa686a73694094e1838ae29aa54d466d6b45aec064c0138a"
    #
    # ids = ["LxAP8PpKzOlG66", "6Kf80yv9CxLy70", "O8zROw_8JyQH_O"]
    # ids = ["LxAP8PpKzOlG66"]

    # threads = []
    # for id_ in ids:
    #     threads.append(Thread(target=thread_get, args=(api_token, id_), daemon=True))
    #     threads[-1].start()
    #
    # for thread in threads:
    #     thread.join()

    # notes = json.load(open("MVP_data/slite.json", "r"))
    # for note in notes:
    #     if notes[note]["client"]:
    #         notes[note]["client"] = [notes[note]["client"]]
    #     else:
    #         notes[note]["client"] = []
    # json.dump(notes, open("MVP_data/slite.json", "w"), indent=4)

    # filter data
    notes = json.load(open("slite_data/Slite.json", "r"))

    for note in notes:
        attributes = {}
        try:
            for index, column in enumerate(notes[note]["columns"]):
                if column == "Tag":
                    s_tags = notes[note]["attributes"][index].lower().split(",")
                    attributes["tags"] = [tag.strip() for tag in s_tags]
                else:
                    attributes[column.lower()] = notes[note]["attributes"][index]
            del notes[note]["columns"]
        except Exception as e:
            print(e)
        finally:
            notes[note]["attributes"] = attributes
            notes[note].update({
                'from': "Slite",
                'client': [],
                'type': 'general',
                'date': '',
            })
            notes[note]["sections"] = asyncio.run(split_markdown_into_sections(notes[note]["content"], heading_level=3))
    #
    #     notes[note]["attributes"] = attributes
    json.dump(notes, open("MVP_data/slite_temp.json", "w"), indent=4)

