import os
import time
from typing import List, Tuple
import requests

from models.wiki_content import WikiContent
from adapters.base import WikiAdapter, WikiAdapterError

class NotionAdapter(WikiAdapter):
    def __init__(self, token: str, notion_version: str):
        if not token:
            raise WikiAdapterError("NOTION_TOKEN is required")
        self.base_url = 'https://api.notion.com/v1'
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Notion-Version': notion_version,
            'Content-Type': 'application/json'
        })

    def _get(self, path: str, params=None):
        r = self.session.get(self.base_url + path, params=params)
        if not r.ok:
            raise WikiAdapterError(f"Notion GET {path} failed: {r.status_code}", {"response": r.text})
        return r.json()

    def _patch(self, path: str, json=None):
        r = self.session.patch(self.base_url + path, json=json)
        if not r.ok:
            raise WikiAdapterError(f"Notion PATCH {path} failed: {r.status_code}", {"response": r.text, "payload": json})
        return r.json()

    def _post(self, path: str, json=None):
        r = self.session.post(self.base_url + path, json=json)
        if not r.ok:
            raise WikiAdapterError(f"Notion POST {path} failed: {r.status_code}", {"response": r.text, "payload": json})
        return r.json()

    def _block_text(self, rich_text: List[dict]) -> str:
        parts = []
        for rt in rich_text or []:
            if 'plain_text' in rt:
                parts.append(rt.get('plain_text', ''))
            elif 'text' in rt:
                parts.append(rt['text'].get('content', ''))
        return ''.join(parts)

    def _blocks_to_markdown(self, blocks: List[dict]) -> str:
        lines = []
        for b in blocks:
            t = b.get('type')
            data = b.get(t, {}) if t else {}
            if t in ('paragraph',):
                lines.append(self._block_text(data.get('rich_text')))
                lines.append('')
            elif t in ('heading_1', 'heading_2', 'heading_3'):
                level = {'heading_1': '#', 'heading_2': '##', 'heading_3': '###'}[t]
                lines.append(f"{level} {self._block_text(data.get('rich_text'))}")
                lines.append('')
            elif t in ('bulleted_list_item',):
                lines.append(f"- {self._block_text(data.get('rich_text'))}")
            elif t in ('numbered_list_item',):
                lines.append(f"1. {self._block_text(data.get('rich_text'))}")
            elif t in ('to_do',):
                checked = data.get('checked', False)
                lines.append(f"- [{'x' if checked else ' '}] {self._block_text(data.get('rich_text'))}")
            elif t in ('quote',):
                lines.append(f"> {self._block_text(data.get('rich_text'))}")
                lines.append('')
            elif t in ('code',):
                lang = data.get('language', 'plain text')
                text = self._block_text(data.get('rich_text'))
                lines.append(f"```{lang}\n{text}\n```")
                lines.append('')
            elif t in ('divider',):
                lines.append('---')
                lines.append('')
            # Ignore unsupported/nested blocks for brevity
        return '\n'.join(lines).strip() + '\n'

    def get_content(self, identifier: dict) -> WikiContent:
        page_id = identifier.get('page_id')
        if not page_id:
            raise WikiAdapterError("Notion get_content requires 'page_id' in identifier")
        # fetch children blocks
        blocks = []
        cursor = None
        while True:
            params = {'page_size': 100}
            if cursor:
                params['start_cursor'] = cursor
            data = self._get(f"/blocks/{page_id}/children", params=params)
            blocks.extend(data.get('results', []))
            if data.get('has_more'):
                cursor = data.get('next_cursor')
            else:
                break
        markdown = self._blocks_to_markdown(blocks)
        title_hint = identifier.get('title') or 'Notion Page'
        return WikiContent(id=page_id, title=title_hint, markdown=markdown, source_url=f"https://www.notion.so/{page_id.replace('-', '')}")

    def upsert_content(self, identifier: dict, content: WikiContent) -> tuple[dict, bool]:
        page_id = identifier.get('page_id')
        if not page_id:
            raise WikiAdapterError("Notion upsert_content requires 'page_id' (creating new pages is not implemented)")
        # Append markdown as code blocks (markdown language)
        chunks = []
        md = content.markdown or ''
        max_len = 1800
        if not md:
            md = content.title or 'Empty content'
        for i in range(0, len(md), max_len):
            chunks.append(md[i:i+max_len])
        children = []
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        # Add a divider and heading to mark sync
        children.append({
            'object': 'block', 'type': 'divider', 'divider': {}
        })
        children.append({
            'object': 'block', 'type': 'paragraph',
            'paragraph': {
                'rich_text': [{
                    'type': 'text', 'text': {'content': f'Synced at {timestamp}'}
                }]
            }
        })
        for ch in chunks:
            children.append({
                'object': 'block', 'type': 'code',
                'code': {
                    'language': 'markdown',
                    'rich_text': [{'type': 'text', 'text': {'content': ch}}]
                }
            })
        self._patch(f"/blocks/{page_id}/children", json={'children': children})
        return ({'page_id': page_id}, False)

