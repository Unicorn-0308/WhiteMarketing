import asyncio
import datetime
from datetime import timezone
import json
import os
import re
import sys
import tempfile
import threading
import time
import logging
import traceback
from pathlib import Path
from threading import Thread, Lock
from urllib.parse import urlparse

import certifi
import nest_asyncio
import requests
from llama_cloud_services import LlamaParse
from tenacity import RetryError
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from config import mongo_info, pinecone_info

# Configuration
SLITE_API_TOKEN = os.environ['SLITE_API_TOKEN']
LLAMA_PARSE_API_KEY = [
    "llx-EIMgSco30xEi3lTt6B71TpHk8LCoTGWEPvy4tSPRFwdTK82Y",
    "llx-DKJwZFD5RMGP071UzwWwRy2lX5ARqS779FaW5COqNO3gYbAv",
    "llx-GYkJfCw4LQgeIyUiBNGe1EVh7kcjLR1OYYEBa4ExEynQx5c1",
    "llx-25CzHcm3sqWj5FB3Di2PVDoUG9gncxfvmnGfKRs11WgZH4XD",
    "llx-mFnF1jUkguCl12XvukCxuoFDJbXY4Y3xsWgVGXYbvIom7cZ8",
    "llx-UBpETVWIiLWVxCQQUiRgjrcUyS8MFPsxQUMrN1Tx3NEKjghB",
    "llx-Bbf43h5VY4ZXv0aXNSjMV4ojuiLPqLGDzkjjAyJOF7PYo79j",
    "llx-P5wi2y54r9ouuZyUguoWNmhVf0M7e9ucz9VACfxD6ocYE7kX",
    "llx-dfqRYoMnb2E9kbAh7ws735W6jxMRbGfJgOBrbLEGOrxFMqoG",
    "llx-Pvn4EUD9GpKY2BRYesvTnjnLJ0Wo4Pyx8ze6Ds7XMlwHLf2y",
    "llx-Em21ZVYzQQpi4ZVEMJFn1Fpuur5zOJv2AknD7lPwcSyrssdo",
    "llx-vVGc6IqgjTbGIea0TuAFPTBv2B4Z8BHccdBmYkurwsIWtmRx",
    "llx-jGCPB8RVHGMvrCnYJIKoe2PTIiBEgYpFkfFooKt15cwW2QFQ",
    "llx-5SXEQ059llV3lYbLVVrNltt1IUip1MSOpglCWvwkUs7cZRv5",
    "llx-H8src4A9ptrsR9E0cwinsr0lbP4nLPTS3KdKIz4hCBpU26Eh",
    "llx-BBU1Ucnp2gfWW3ncKNI7l7xi0AMw9KcALjsIv3Ymc17HSDa9",
    "llx-Bmebz35LhtLTw2zFEV3s9G1QkKpSKmxnCzbFaKnhdCjYaVID",
    "llx-gpl5WbyHtth6SlL5HkKivUH1A3hWqVkN5XqYSlrHcqNwbvcg",
    "llx-CGLvq2jNTJVhUSZ2ziMBdqWmoPGQStyjex7kqr4gcPZQq4QY",
    "llx-9yTFUTZ7ok0jKsJcP2x3ZG5kCpX3zKnPuww3RZ2tC9PXWsJH",
    "llx-VPiwAq8eTr99UCfbhINfcds37DcJ5HrxlT0WeHiMQycOiEEP",
    "llx-9PEfzqG66yUb5uTp9wjAFMfpDVc2Z6Oc1u2P2tCRHC1rO5uY",
    "llx-cxmsp0FTaJhFoeeCH4zJgs6UQg1x3gIhzPVx44Dm7vNboBbf",
    "llx-HyVeAJ2yFTnzvZfSl0pDykBYAaTQlHHsexruf36BrqdvkrpT",
    "llx-bQZvsP5szl3niPfouWK6ta8tXRLduaZNizyKaXhAEhxZFKsy",
    "llx-DZjNxViowtDKtUINBMtCz6BjYWg5DKufJdeZhZTjDWR6OEF1",
    "llx-htInYFGncqyVH3fB1rSQBqJSLjhFYcivQoihX8ACVF98V41k",
    "llx-CQHgOBDORB0JqkFxMO6zNGQqdgD0f2uA1gyutayAt8pTeY7U",
    "llx-KK9s90oqAudZyuaEQbnGcqeY8NhN1i6Zfl6vx8DXwZMGboWe",
    "llx-QV2Yq5zqpBdxQEXU6saeZZl4ARb17asG3GjrOgT5GD06Jb3t",
    "llx-apGKkOLQU79oFOo1urFipPevqiQDDe1WRfCbbLVENnjNrb3S",
    "llx-FguSkV0asQxnZHLIHCR2zRNce0oeJPYF1wczk3jo2a4LRcOb",
    "llx-bN9Eemg2hldEdqquqTD5x2FsjwFk4K19TAss4eV1Nppoca8O",
    "llx-YQC7Uyyjvlmi70yngfTnOav3lp5kFX8sekskGbQ42yiM7qTD",
    "llx-T90rpo8jASP8xNBQvYAk8pi4VK2O594lEpgbhsIUW2KgbgVU",
    "llx-CFmurfB4y29wAbt9lLkrB1E1v4FZeYgu9IqBr9pzDkafGdQG",
]
llama_key_index = 0
MONGODB_URI = mongo_info["url"]

# Settings
INDEX_NAME = pinecone_info["index"]
NAMESPACE = pinecone_info["env"]
DB_NAME = mongo_info["database"]
COLLECTION_NAME = mongo_info["collection"]

# Channel IDs
GENERAL_CHANNELS = [
    "2OFMvfIM2TZvrO", "JGD1gJ-QQFeJAh", "-5F-g9KjWkhYcR", 
    "Oxecg6_WR7Yz_1", "g9dRwLVPtEBF8d", "Vc8CR1prbgkIx8", 
    "mTkRo1Mqtv2t0H", "gCTl9dusvIlL1H"
]
CLIENT_CHANNEL = ["D7i85zrvuNfJYE", "KA3k0sWir4Ll2n"]

total_updated = 0

# Global clients
ai_client = OpenAI()
pc = None
mongo_collection = None

# Global variables for threading
log_lock = Lock()
error_lock = Lock()
progress_lock = Lock()

# Setup logging
def setup_logging():
    """Setup logging configuration"""
    try:
        # Clear log files
        with open('log.txt', 'w') as f:
            f.write(f"=== Slite Export Started at {datetime.datetime.now()} ===\n")
        with open('error.txt', 'w') as f:
            f.write(f"=== Error Log Started at {datetime.datetime.now()} ===\n")
        print("Logging system initialized successfully")
    except Exception as e:
        print(f"Failed to setup logging: {e}")

def log_info(message):
    """Thread-safe logging to log.txt"""
    try:
        with log_lock:
            with open('log.txt', 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now()}: {message}\n")
            print(f"INFO: {message}")
    except Exception as e:
        print(f"Failed to log info message: {e}")

def log_error(message, error=None):
    """Thread-safe error logging to error.txt"""
    try:
        with error_lock:
            with open('error.txt', 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now()}: {message}\n")
                if error:
                    f.write(f"Error details: {str(error)}\n")
                    f.write(f"Traceback: {traceback.format_exc()}\n===========================================================\n")
            print(f"ERROR: {message}")
    except Exception as e:
        print(f"Failed to log error message: {e}")

# Helper Functions from slite_template.py
def extract_image_urls_from_line(line):
    """Extracts all image URLs from a single line of Markdown."""
    try:
        urls_found = []
        
        # 1. Standard Markdown image syntax: ![alt](url)
        markdown_image_regex = r"!\[[^\]]*\]\((?P<url>[^)\s]+?)(?:\s+[\"'].*?[\"'])?\)"
        for match in re.finditer(markdown_image_regex, line):
            url = match.group("url").strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        # 2. HTML img tags: <img src="url">
        html_img_regex = r'<img[^>]*\s+src\s*=\s*["\']([^"\']+)["\'][^>]*>'
        for match in re.finditer(html_img_regex, line, re.IGNORECASE):
            url = match.group(1).strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        # 3. Direct image URLs (http/https URLs with image extensions)
        image_extensions = r'\.(jpg|jpeg|png|gif|bmp|tiff|webp|svg|ico)'
        direct_url_regex = r'https?://[^\s\)"\'\]<>]+' + image_extensions + r'(?:\?[^\s\)"\'\]<>]*)?'
        for match in re.finditer(direct_url_regex, line, re.IGNORECASE):
            url = match.group(0).strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        # 4. URLs in parentheses or brackets that might be images
        # This catches cases like (https://example.com/image.jpg) or [https://example.com/image.jpg]
        bracketed_url_regex = r'[\(\[]([^)\]]*https?://[^\s\)"\'\]<>]+' + image_extensions + r'(?:\?[^\s\)"\'\]<>]*)?)[)\]]'
        for match in re.finditer(bracketed_url_regex, line, re.IGNORECASE):
            url = match.group(1).strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        # 5. Quoted image URLs
        quoted_url_regex = r'["\']([^"\']*https?://[^\s"\'<>]+' + image_extensions + r'(?:\?[^\s"\'<>]*)?)["\']'
        for match in re.finditer(quoted_url_regex, line, re.IGNORECASE):
            url = match.group(1).strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        # 6. Image URLs in common hosting platforms (even without obvious extensions)
        platform_regex = r'https?://(?:(?:i\.)?imgur\.com|(?:media\.)?giphy\.com|(?:images\.)?unsplash\.com|(?:cdn\.)?pixabay\.com|(?:images\.)?pexels\.com|(?:www\.)?flickr\.com/photos)/[^\s\)"\'\]<>]+'
        for match in re.finditer(platform_regex, line, re.IGNORECASE):
            url = match.group(0).strip()
            if url and url not in urls_found:
                urls_found.append(url)
        
        if urls_found:
            log_info(f"Found {len(urls_found)} image URL(s) in line: {urls_found}")
        
        return urls_found
    except Exception as e:
        log_error(f"Error extracting image URLs from line: {line[:100]}", e)
        return []

def get_url_extension(url, content_type_header=None):
    """Tries to determine a file extension from the URL path or Content-Type header."""
    try:
        parsed_url_path = urlparse(url).path
        try:
            ext = os.path.splitext(parsed_url_path)[1].lower()
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:
                return ext
        except Exception:
            pass
        
        if content_type_header:
            content_type = content_type_header.lower()
            if 'image/png' in content_type:
                return '.png'
            elif 'image/jpeg' in content_type or 'image/jpg' in content_type:
                return '.jpg'
            elif 'image/gif' in content_type:
                return '.gif'
            elif 'image/bmp' in content_type:
                return '.bmp'
            elif 'image/tiff' in content_type:
                return '.tiff'
        
        log_info("Warning: Could not reliably determine image extension. Defaulting to .png")
        return ".png"
    except Exception as e:
        log_error(f"Error determining URL extension for {url}", e)
        return ".png"

async def parse_image_from_url_with(image_url: str):
    """Downloads an image from a URL and parses it using LlamaParse to extract text."""
    log_info(f"Attempting to download image from: {image_url}")
    temp_file_path = None
    global llama_key_index
    
    try:
        # Download image - if this fails, stop here
        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()
        
        file_extension = get_url_extension(image_url, response.headers.get('Content-Type'))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_file_path = tmp_file.name
        
        log_info(f"Successfully downloaded image: {image_url}")
        
    except requests.exceptions.RequestException as e:
        log_error(f"Error downloading image: {image_url}", e)
        return None
    
    # Parse image with infinite retry on parsing errors
    result = None
    while True:
        try:
            parser = LlamaParse(
                api_key=LLAMA_PARSE_API_KEY[llama_key_index],
                verbose=True,
                premium_mode=True,
                num_workers=4
            )
            
            result = await parser.aparse(file_path=temp_file_path)

            break
                
        except Exception as e:
            if isinstance(e, RetryError):
                log_error(f"Error during LlamaParse processing:, {type(e)} {e}. Retrying in 10 seconds...", e)
                await asyncio.sleep(10)  # Wait 10 seconds before retry
                with progress_lock:
                    llama_key_index += 1
                    if llama_key_index >= len(LLAMA_PARSE_API_KEY):
                        llama_key_index = 0
                continue
            else:
                break

    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.remove(temp_file_path)
            log_info(f"Temporary file {temp_file_path} deleted.")
        except Exception as e:
            log_error(f"Error deleting temporary file {temp_file_path}", e)

    if result:
        log_info(f"Successfully parsed image: {image_url}")
        return result.get_markdown_documents()[0].text
    else:
        log_error(f"LlamaParse did not return any documents for: {image_url}")
        return None

async def split_markdown_into_sections(markdown_content, heading_level=3, parse_images=True):
    """Splits markdown content into sections based on a specified heading level."""
    try:
        sections = []
        current_section_lines = []
        current_title = "Header"
        original_heading_line = ""
        
        lines = markdown_content.splitlines()
        
        for line in lines:
            flag = False
            for num in range(1, heading_level + 1):
                heading_prefix = "#" * num + " "
                if line.startswith(heading_prefix):
                    if current_section_lines or (current_title != "Header" and not sections):
                        if not (current_title == "Header" and not "".join(current_section_lines).strip()):
                            sections.append({
                                "title": current_title,
                                "content": "\n".join(current_section_lines).strip(),
                                "original_heading_line": original_heading_line
                            })
                    
                    current_title = line[len(heading_prefix):].strip()
                    original_heading_line = line
                    current_section_lines = [line]
                    flag = True
                    break
            
            if not flag:
                current_section_lines.append(line)
                image_urls = extract_image_urls_from_line(line)
                for url in image_urls:
                    if parse_images:
                        try:
                            export_data = await parse_image_from_url_with(url)
                            if export_data:
                                current_section_lines.extend(export_data.splitlines())
                        except Exception as e:
                            log_error(f"Error parsing image {url}", e)
                    else:
                        log_info(f"Detected image URL extension for {url}")
        
        # Add the last accumulated section
        if current_section_lines or (current_title != "Header" and not sections):
            if not (current_title == "Header" and not "".join(current_section_lines).strip()):
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_section_lines).strip(),
                    "original_heading_line": original_heading_line
                })
        elif not sections and not current_section_lines and current_title == "Header" and markdown_content.strip():
            sections.append({
                "title": "Content",
                "content": markdown_content.strip(),
                "original_heading_line": ""
            })
        
        result = {}
        for sec in sections:
            result[sec["title"]] = sec["content"]
        
        log_info(f"Successfully split markdown into {len(result)} sections")
        return result
    except Exception as e:
        log_error("Error splitting markdown into sections", e)
        return {"Content": markdown_content}

def process_attributes_and_columns(doc_data):
    """Process and combine attributes and columns fields into a single attributes object."""
    try:
        if "columns" in doc_data and "attributes" in doc_data:
            new_attributes = {}
            try:
                for index, column in enumerate(doc_data["columns"]):
                    if column == "tags" or column == "owner":
                        s_tags = doc_data["attributes"][index].split(",")
                        new_attributes[column.lower()] = [tag.strip() if column == "tags" else tag.strip().replace("@", "") for tag in s_tags]
                    else:
                        new_attributes[column.lower()] = doc_data["attributes"][index]
                
                # Remove the columns field
                del doc_data["columns"]
                
            except Exception as e:
                log_error(f"Error processing columns and attributes for doc {doc_data.get('id', 'unknown')}", e)
                new_attributes = doc_data.get("attributes", {})
            finally:
                doc_data["attributes"] = new_attributes
                log_info(f"Successfully processed attributes for doc {doc_data.get('id', 'unknown')}")
        
        return doc_data
    except Exception as e:
        log_error(f"Error in process_attributes_and_columns for doc {doc_data.get('id', 'unknown')}", e)
        return doc_data

# Core Functions from slite_export.py (modified)
def get_response(url, headers, name, interval=60):
    """Get HTTP response with retry logic for rate limiting."""
    try:
        response = requests.get(url, headers=headers)
        while response.status_code == 429 or response.status_code == 503:
            log_info(f"{name} {url} {response.status_code} - Rate limited, waiting 10 seconds")
            time.sleep(10)
            response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            log_info(f"Successfully fetched: {name} {url}")
        else:
            log_error(f"HTTP error for {name} {url}: {response.status_code} - {response.text}")
        
        return response
    except Exception as e:
        log_error(f"Error making request to {url}", e)
        raise

async def get_doc(doc_gid: str, headers, client=[], type_="general", s_format="%m/%d/%Y", parse_images=True):
    """Get a document and all its children recursively."""
    result = {}
    response = None
    try:
        log_info(f"Processing document: {doc_gid} (type: {type_}, client: {client})")
        
        response = get_response(f"https://api.slite.com/v1/notes/{doc_gid}", headers=headers, name="doc")
        if response.status_code != 200:
            log_error(f"Error fetching doc {doc_gid}: {response.status_code} - {response.text}")
            return result
        
        doc_self = response.json()

        need_update = True
        mongo_self = list(mongo_collection.find({"id": doc_gid}))
        if len(mongo_self) and mongo_self[0]["updatedAt"].replace(tzinfo=timezone.utc) >= datetime.datetime.fromisoformat(doc_self['updatedAt']):
            need_update = False

        if need_update:
            # Process attributes and columns
            doc_self = process_attributes_and_columns(doc_self)

            # Determine date for weekly/monthly reviews
            date = ""
            if type_ in ["weekly", "monthly"]:
                try:
                    date_matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", doc_self['title'])
                    if date_matches:
                        try:
                            date = datetime.datetime.strptime(date_matches[0], s_format).date().strftime('%Y-%m-%d')
                        except ValueError:
                            log_error(f"Error parsing date {doc_gid}: {s_format} - {doc_self['title']}")
                            date = datetime.datetime.strptime(date_matches[0], "%m/%d/%Y" if s_format == "%d/%m/%Y" else "%d/%m/%Y").date().strftime('%Y-%m-%d')
                except Exception as e:
                    log_error(f"Error parsing date from title: {doc_self['title']}", e)

            # Process content into sections (parse images based on parameter)
            sections = await split_markdown_into_sections(doc_self['content'], heading_level=3, parse_images=parse_images)

            # Update document with required fields
            doc_self.update({
                "sections": sections,
                "from": "Slite",
                "client": client,
                "type": type_,
                "date": date,
                "children": []
            })

            result[doc_self["id"]] = doc_self
            log_info(f"Successfully processed document: {doc_self['id']} - {doc_self['title']}")
        else:
            result[doc_self["id"]] = mongo_self[0]

        # Get children
        cursor = ""
        while True:
            try:
                response = get_response(f"https://api.slite.com/v1/notes/{doc_gid}/children?cursor={cursor}", headers=headers, name="doc_children")
                children = response.json()
                
                for child in children["notes"]:
                    result[doc_self["id"]]["children"] = []
                    result[doc_self["id"]]["children"].append(child["id"])
                    
                    # Determine child type and client
                    child_client = client
                    child_type = type_

                    is_review = False
                    if doc_self["title"].lower().find("weekly reviews") != -1 and len(client):
                        child_type = "weekly"
                        is_review = True
                    elif doc_self["title"].lower().find("monthly reviews") != -1 and len(client):
                        child_type = "monthly"
                        is_review = True

                    s_format = "%d/%m/%Y"
                    if is_review:
                        try:
                            for c in children["notes"]:
                                date_matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", c['title'])
                                if date_matches:
                                    datetime.datetime.strptime(date_matches[0], s_format).date()
                        except Exception as e:
                            s_format = "%m/%d/%Y"
                    
                    # Recursively get child
                    child_result = await get_doc(child["id"], headers, child_client, child_type, s_format, parse_images)
                    result.update(child_result)
                
                if not children["hasNextPage"]:
                    break
                cursor = children["nextCursor"]
            except Exception as e:
                log_error(f"Error fetching children for doc {doc_gid}", e)
                break
        
        log_info(f"Completed processing document and children: {doc_self['id']} - {doc_self['title']}")

        if need_update:
            # Upsert this document after all children are processed
            await upsert_document(doc_self)
            global total_updated
            total_updated += 1
        
    except Exception as e:
        log_error(f"Error processing doc {doc_gid}", e)
        if response:
            log_error(f"Response content: {response.text}")
    
    return result

# Upsert Functions (modified from slite_upsert.py)
async def upsert_document(doc):
    """Upsert a single document to MongoDB and Pinecone."""
    try:
        log_info(f"Upserting document: {doc.get('id', 'unknown')} - {doc.get('title', 'Unknown Title')}")
        
        # Prepare document for MongoDB (convert dates)
        mongo_doc = doc.copy()
        try:
            if mongo_doc.get('updatedAt'):
                mongo_doc['updatedAt'] = datetime.datetime.fromisoformat(mongo_doc['updatedAt'])
            if mongo_doc.get('createdAt'):
                mongo_doc['createdAt'] = datetime.datetime.fromisoformat(mongo_doc['createdAt'])
            if mongo_doc.get('date') and mongo_doc['date']:
                # Convert YYYY-MM-DD format to datetime
                mongo_doc['date'] = datetime.datetime.strptime(mongo_doc['date'], '%Y-%m-%d')
        except ValueError as e:
            log_error(f"Date conversion error for doc {doc.get('id', 'unknown')}", e)
        
        # Upsert to MongoDB
        mongo_collection.update_one({"id": mongo_doc["id"]}, {"$set": mongo_doc}, upsert=True)
        log_info(f"MongoDB upserted: {doc['id']}")
        
        # Upsert to Pinecone (only if content is not empty)
        if doc.get('sections') and any(content.strip() for content in doc['sections'].values()):
            await upsert_to_pinecone(doc)
        else:
            log_info(f"Skipping Pinecone upsert for doc {doc['id']} - no content in sections")
        
    except Exception as e:
        log_error(f"Error upserting document {doc.get('id', 'unknown')}", e)

async def upsert_to_pinecone(doc):
    """Upsert document sections to Pinecone."""
    try:
        inputs = []
        section_titles = []
        
        # Prepare inputs for embedding
        for section_title, section_content in doc['sections'].items():
            if section_content.strip():  # Only non-empty sections
                inputs.append(section_content)
                section_titles.append(section_title)
        
        if not inputs:
            log_info(f"No content to upsert to Pinecone for doc {doc['id']}")
            return
        
        # Get embeddings
        response = ai_client.embeddings.create(
            model='text-embedding-3-small',
            input=inputs
        ).data
        
        # Prepare records for Pinecone
        records = []
        for i, (section_title, embedding) in enumerate(zip(section_titles, response)):
            records.append({
                'id': f"{doc['id']}-{i}".lower(),
                'values': embedding.embedding,
                'metadata': {
                    'from': doc['from'],
                    'client': doc['client'],
                    'type': doc['type'],
                    'date': doc['date'] if doc['date'] else '',
                    'id': doc['id'],
                    'section': section_title,
                }
            })
        
        # Upsert to Pinecone
        index_model = pc.Index(INDEX_NAME)
        index_model.upsert(records, namespace=NAMESPACE)
        log_info(f"Pinecone upserted: {doc['id']} ({len(records)} sections)")
        
    except Exception as e:
        log_error(f"Error upserting to Pinecone for doc {doc.get('id', 'unknown')}", e)

# Main Processing Functions
async def process_general_channel(channel_id, headers):
    """Process a general channel."""
    try:
        log_info(f"Processing general channel: {channel_id}")
        # Don't parse images in Step One
        result = await get_doc(channel_id, headers, client=[], type_="general", parse_images=False)
        log_info(f"Successfully completed general channel: {channel_id}")
        return result
    except Exception as e:
        log_error(f"Error processing general channel {channel_id}", e)
        return {}

async def process_client_channel(headers, id):
    """Process the client channel with special logic."""
    try:
        log_info(f"Processing client channel: {id}")
        
        # Get the main client channel
        response = get_response(f"https://api.slite.com/v1/notes/{id}", headers=headers, name="client_channel")
        if response.status_code != 200:
            log_error(f"Error fetching client channel: {response.status_code} - {response.text}")
            return {}
        
        channel_doc = response.json()

        need_update = True
        mongo_self = list(mongo_collection.find({"id": id}))
        print(mongo_self[0]["updatedAt"].replace(tzinfo=timezone.utc), datetime.datetime.fromisoformat(channel_doc['updatedAt']))
        if len(mongo_self) and mongo_self[0]["updatedAt"].replace(tzinfo=timezone.utc) >= datetime.datetime.fromisoformat(channel_doc['updatedAt']):
            need_update = False

        if need_update:
            # Process attributes and columns for channel doc
            channel_doc = process_attributes_and_columns(channel_doc)

            channel_doc.update({
                "sections": await split_markdown_into_sections(channel_doc['content'], heading_level=3, parse_images=True),
                "from": "Slite",
                "client": [],
                "type": "general",
                "date": "",
                "children": []
            })

            result = {channel_doc["id"]: channel_doc}
        else:
            result = {channel_doc["id"]: mongo_self[0]}

        # Get children of client channel
        cursor = ""
        client_threads = []
        
        while True:
            try:
                response = get_response(f"https://api.slite.com/v1/notes/{id}/children?cursor={cursor}", headers=headers, name="client_children")
                children = response.json()

                for child in children["notes"]:
                    result[channel_doc["id"]]["children"].append(child["id"])

                    # Check if child title starts with three digits (client-related)
                    if child["title"][:3].isnumeric():
                        client_id = child["title"][:3]
                        log_info(f"Found client subdoc: {child['title']} (Client ID: {client_id})")

                        # Process client subdoc in a separate thread
                        def run_client_subdoc(subdoc_id, client_id_param):
                            try:
                                asyncio.run(process_client_subdoc(subdoc_id, client_id_param, headers, result))
                            except Exception as e:
                                log_error(f"Error in client subdoc thread for {subdoc_id}", e)

                        thread = Thread(
                            target=run_client_subdoc,
                            args=(child["id"], client_id),
                            daemon=True
                        )
                        client_threads.append(thread)
                        thread.start()
                    else:
                        # Process as general doc (with image parsing in Step Two)
                        try:
                            general_result = await get_doc(child["id"], headers, client=[], type_="general", parse_images=True)
                            result.update(general_result)
                        except Exception as e:
                            log_error(f"Error processing general doc {child['id']}", e)
                
                if not children["hasNextPage"]:
                    break
                cursor = children["nextCursor"]
            except Exception as e:
                log_error(f"Error fetching client channel children", e)
                break
        
        # Wait for all client threads to complete
        log_info(f"Waiting for {len(client_threads)} client threads to complete...")
        for i, thread in enumerate(client_threads):
            try:
                thread.join()
                log_info(f"Client thread {i+1}/{len(client_threads)} completed")
            except Exception as e:
                log_error(f"Error joining client thread {i+1}", e)

        if need_update:
            # Upsert the main channel document
            await upsert_document(channel_doc)
        
        log_info(f"Successfully completed client channel: {id}")
        return result
        
    except Exception as e:
        log_error(f"Error processing client channel", e)
        return {}

async def process_client_subdoc(subdoc_id, client_id, headers, result_dict):
    """Process a client subdoc and its children."""
    try:
        log_info(f"Processing client subdoc: {subdoc_id} (Client: {client_id})")
        # Parse images in Step Two (client processing)
        client_result = await get_doc(subdoc_id, headers, client=[client_id], type_="client_spec", parse_images=True)
        
        # Thread-safe update of result dictionary
        with threading.Lock():
            result_dict.update(client_result)
        
        log_info(f"Successfully completed client subdoc: {subdoc_id} (Client: {client_id})")
        
    except Exception as e:
        log_error(f"Error processing client subdoc {subdoc_id} (Client: {client_id})", e)

def setup_connections():
    """Setup MongoDB and Pinecone connections."""
    global pc, mongo_collection
    
    try:
        log_info("Setting up database connections...")
        
        # Setup Pinecone
        try:
            pc = Pinecone()
            if not pc.has_index(INDEX_NAME):
                pc.create_index(
                    name=INDEX_NAME,
                    vector_type="dense",
                    dimension=1536,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1",
                    ),
                    deletion_protection="disabled",
                    tags={
                        "environment": NAMESPACE,
                    }
                )
                log_info(f"Created Pinecone index: {INDEX_NAME}")
            else:
                log_info(f"Connected to existing Pinecone index: {INDEX_NAME}")
        except Exception as e:
            log_error("Failed to setup Pinecone connection", e)
            raise
        
        # Setup MongoDB
        try:
            client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
            client.admin.command('ismaster')
            mongo_collection = client[DB_NAME][COLLECTION_NAME]
            log_info("MongoDB connection successful!")
        except ConnectionFailure as e:
            log_error("MongoDB connection failed!", e)
            sys.exit(1)
        except Exception as e:
            log_error("Unexpected error connecting to MongoDB", e)
            sys.exit(1)
        
        log_info("Database connections setup completed successfully")
        
    except Exception as e:
        log_error("Critical error during database setup", e)
        raise

async def main():
    """Main execution function."""
    global total_updated
    total_updated = 0
    try:
        log_info("=== Starting Slite Export and Upsert Process ===")
        
        nest_asyncio.apply()
        
        # Setup logging
        setup_logging()
        
        # Setup connections
        setup_connections()
        
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {SLITE_API_TOKEN}"
        }
        
        # Step One: Process general channels
        log_info("\n=== STEP ONE: Processing General Channels ===")
        general_threads = []

        def run_general_channel(channel_id):
            try:
                asyncio.run(process_general_channel(channel_id, headers))
            except Exception as e:
                log_error(f"Error in general channel thread for {channel_id}", e)

        for channel_id in GENERAL_CHANNELS:
            try:
                thread = Thread(
                    target=run_general_channel,
                    args=(channel_id,),
                    daemon=True
                )
                general_threads.append(thread)
                thread.start()
                log_info(f"Started thread for general channel: {channel_id}")
            except Exception as e:
                log_error(f"Failed to start thread for general channel {channel_id}", e)

        # Wait for all general channel threads to complete
        log_info(f"Waiting for {len(general_threads)} general channel threads to complete...")
        for i, thread in enumerate(general_threads):
            try:
                thread.join()
                log_info(f"General channel thread {i+1}/{len(general_threads)} completed")
            except Exception as e:
                log_error(f"Error joining general channel thread {i+1}", e)
        
        # Step Two: Process client channel
        log_info("\n=== STEP TWO: Processing Client Channel ===")
        for id in CLIENT_CHANNEL:
            await process_client_channel(headers, id)
        
        log_info("\n=== EXPORT AND UPSERT PROCESS COMPLETED SUCCESSFULLY ===")
        
    except Exception as e:
        log_error("Critical error in main execution", e)
        raise

    return total_updated

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1) 