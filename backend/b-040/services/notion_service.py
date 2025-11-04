import os
import requests
from typing import Dict, Any, List

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = os.getenv('NOTION_VERSION', '2022-06-28')


def _chunk_text(text: str, max_len: int = 1800) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_len, n)
        chunks.append(text[start:end])
        start = end
    return chunks


def _paragraph_block(text: str) -> Dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text}
                }
            ]
        }
    }


def _heading_block(text: str, level: int = 1) -> Dict[str, Any]:
    t = f"heading_{level}"
    return {
        "object": "block",
        "type": t,
        t: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text}
                }
            ]
        }
    }


def export_to_notion(title: str, content: str, options: Dict[str, Any], settings) -> Dict[str, Any]:
    token = settings.NOTION_API_TOKEN
    parent_page_id = options.get('notion_parent_page_id') or settings.NOTION_PARENT_PAGE_ID
    database_id = options.get('notion_database_id') or settings.NOTION_DATABASE_ID
    title_prop = options.get('notion_title_property') or settings.NOTION_TITLE_PROPERTY

    if not token:
        raise ValueError("NOTION_API_TOKEN is not configured")
    if not (parent_page_id or database_id):
        raise ValueError("NOTION_PARENT_PAGE_ID or NOTION_DATABASE_ID must be configured")

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

    children = [_heading_block(title, 1)]
    for chunk in _chunk_text(content or ''):
        children.append(_paragraph_block(chunk))

    body: Dict[str, Any] = {
        "parent": {},
        "children": children,
    }

    if database_id:
        body["parent"] = {"database_id": database_id}
        body["properties"] = {
            title_prop: {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title or 'Untitled'}
                    }
                ]
            }
        }
    else:
        body["parent"] = {"page_id": parent_page_id}
        body["properties"] = {
            "title": [
                {
                    "type": "text",
                    "text": {"content": title or 'Untitled'}
                }
            ]
        }

    resp = requests.post(NOTION_API_URL, headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Notion API error {resp.status_code}: {resp.text}")

    data = resp.json()
    page_id = data.get('id')
    url = data.get('url')
    return {"id": page_id, "url": url}

