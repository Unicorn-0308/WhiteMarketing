import re
import json
import os
import asyncio
from pathlib import Path

import requests
from urllib.parse import urlparse
import tempfile
from llama_cloud_services import LlamaParse

def extract_image_urls_from_line(line):
    """
    Extracts image URLs from a single line of Markdown.
    Handles Markdown image syntax.
    """
    markdown_image_regex = r"!\[[^\]]*\]\((?P<url>[^)\s]+?)(?:\s+[\"'].*?[\"'])?\)"
    urls_found = []

    # Find Markdown images
    # re.finditer returns an iterator yielding match objects
    for match in re.finditer(markdown_image_regex, line):
        urls_found.append(match.group("url")) # Access the named group 'url'

    return urls_found

def get_url_extension(url, content_type_header=None):
    """
    Tries to determine a file extension from the URL path or Content-Type header.
    """
    # Try from URL path first
    parsed_url_path = urlparse(url).path
    try:
        ext = os.path.splitext(parsed_url_path)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']:  # Add more if needed
            return ext
    except Exception:
        pass

    # Try from Content-Type header
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

    # Default or if unsure
    print("Warning: Could not reliably determine image extension. Defaulting to .png")
    return ".png"  # Default if cannot determine, LlamaParse might still figure it out

async def parse_image_from_url_with(image_url: str):
    """
    Downloads an image from a URL, saves it temporarily,
    and parses it using LlamaParse to extract text.
    """
    print(f"Attempting to download image from: {image_url}")
    temp_file_path = None
    try:
        # 1. Download the image
        response = requests.get(image_url, stream=True, timeout=30)  # Add timeout
        response.raise_for_status()  # Raise an exception for bad status codes

        # Determine the file extension for the temporary file
        file_extension = get_url_extension(image_url, response.headers.get('Content-Type'))

        # 2. Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
            temp_file_path = tmp_file.name

        # 3. Initialize LlamaParse
        parser = LlamaParse(
            api_key="llx-UmER6nt9U0cNtNSiYWe9e2EKYzgfRO2RSwfMOGIIQ0Nts5hr",
            verbose=True,
            premium_mode=True,
            num_workers=4
        )

        # 4. Parse the temporary image file
        result = await parser.aparse(file_path=temp_file_path)

        # 5. Process result
        if result:
            return result.get_markdown_documents()[0].text
        else:
            print("LlamaParse did not return any documents.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error downloading image: {e}", image_url)
        return None
    except Exception as e:
        print(f"An error occurred during LlamaParse processing: {e}", image_url)
        return None
    finally:
        # 6. Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"Temporary file {temp_file_path} deleted.")
            except Exception as e:
                print(f"Error deleting temporary file {temp_file_path}: {e}")

def sanitize_filename(name):
    """
    Sanitizes a string to be used as a valid filename.
    Removes or replaces characters that are problematic in filenames.
    """
    name = re.sub(r'[^\w\s-]', '', name)  # Remove non-alphanumeric, non-space, non-hyphen
    name = re.sub(r'[-\s]+', '-', name).strip('-_') # Replace spaces/hyphens with single hyphen
    return name[:50] # Limit length for safety

async def split_markdown_into_sections(markdown_content, heading_level=2):
    """
    Splits markdown content into sections based on a specified heading level.

    Args:
        markdown_content (str): The full markdown string.
        heading_level (int): The heading level to split by (e.g., 2 for ##, 3 for ###).

    Returns:
        list: A list of dictionaries, where each dictionary has:
              {'title': str, 'content': str, 'original_heading_line': str}
              The 'content' does NOT include the heading line that defined the section,
              unless it's the very first part of the document before any recognized heading.
    """
    sections = []
    current_section_lines = []
    current_title = "Header"  # Default for content before the first specified heading
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

                # Start a new section
                current_title = line[len(heading_prefix):].strip()
                original_heading_line = line
                current_section_lines = [line]
                flag = True
                break
        if not flag:
            current_section_lines.append(line)
            image_urls = extract_image_urls_from_line(line)
            for url in image_urls:
                # export_data = await parse_image_from_url_with(url)
                export_data = ''
                try:
                    current_section_lines.extend(export_data.splitlines())
                except Exception as e:
                    print(e)


    # Add the last accumulated section after the loop
    if current_section_lines or (current_title != "Header" and not sections):
        if not (current_title == "Header" and not "".join(current_section_lines).strip()):
            sections.append({
                "title": current_title,
                "content": "\n".join(current_section_lines).strip(),
                "original_heading_line": original_heading_line
            })
    elif not sections and not current_section_lines and current_title == "Header" and markdown_content.strip():
        # Handle case where the entire document has no target headings
        # and should be treated as a single "Header" section.
        sections.append({
            "title": "Content", # Or keep "Header"
            "content": markdown_content.strip(),
            "original_heading_line": ""
        })

    result = {}
    for sec in sections:
        result[sec["title"]] = sec["content"]

    return result

def split_markdown_by_horizontal_rule(markdown_content):
    """
    Splits markdown content into sections based on horizontal rules (--- or ***).
    Note: This is less semantically robust than splitting by headings.
    """
    parts = re.split(r'\n\s*(?:-{3,}|\*{3,})\s*\n', markdown_content)
    sections = []
    for i, part_content in enumerate(parts):
        part_content = part_content.strip()
        if part_content:
            title_candidate = part_content.splitlines()[0] if part_content else f"Section {i+1}"
            if title_candidate.startswith("#"):
                title = re.sub(r'^#+\s*', '', title_candidate).strip()
            else:
                title = f"Section {i+1}"

            sections.append({
                "title": title,
                "content": part_content,
                "original_heading_line": "" # Not applicable here
            })

    result = {}
    for sec in sections:
        result[sec["title"]] = sec["content"]

    return result


if __name__ == "__main__":
    with open("slite_data/notes.json", "r") as f:
        data = json.load(f)["nRxTc7Rog0Th0K"]

    content = data["content"]

    print("--- Splitting by H2 Headings ---")
    data['sections_by_heading'] = split_markdown_into_sections(content, heading_level=3)

    print("\n\n--- Splitting by Horizontal Rules (--- or ***) ---")
    data['sections_by_hr'] = split_markdown_by_horizontal_rule(content)