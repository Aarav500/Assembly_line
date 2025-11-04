from __future__ import annotations
import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Tuple

from models.wiki_content import WikiContent
from adapters.base import WikiAdapter, WikiAdapterError
from utils.markdown_conv import html_to_markdown, markdown_to_html

class ConfluenceAdapter(WikiAdapter):
    def __init__(self, base_url: str, username: str, api_token: str):
        if not base_url or not username or not api_token:
            raise WikiAdapterError("Confluence base_url, username and api_token are required")
        self.base_url = base_url.rstrip('/')
        self.api = self.base_url + '/rest/api'
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, api_token)
        self.session.headers.update({'Content-Type': 'application/json'})

    def _get(self, path: str, params=None):
        r = self.session.get(self.api + path, params=params)
        if not r.ok:
            raise WikiAdapterError(f"Confluence GET {path} failed: {r.status_code}", {"response": r.text})
        return r.json()

    def _put(self, path: str, json=None):
        r = self.session.put(self.api + path, json=json)
        if not r.ok:
            raise WikiAdapterError(f"Confluence PUT {path} failed: {r.status_code}", {"response": r.text, "payload": json})
        return r.json()

    def _post(self, path: str, json=None):
        r = self.session.post(self.api + path, json=json)
        if not r.ok:
            raise WikiAdapterError(f"Confluence POST {path} failed: {r.status_code}", {"response": r.text, "payload": json})
        return r.json()

    def _find_page_by_title(self, space_key: str, title: str) -> Optional[dict]:
        params = {'spaceKey': space_key, 'title': title, 'expand': 'version'}
        data = self._get('/content', params=params)
        results = data.get('results', [])
        return results[0] if results else None

    def get_content(self, identifier: dict) -> WikiContent:
        page_id = identifier.get('page_id')
        if not page_id:
            space_key = identifier.get('space_key')
            title = identifier.get('title')
            if not space_key or not title:
                raise WikiAdapterError("Confluence get_content requires 'page_id' or ('space_key' and 'title')")
            page = self._find_page_by_title(space_key, title)
            if not page:
                raise WikiAdapterError("Confluence page not found", {"space_key": space_key, "title": title})
            page_id = page.get('id')
        page = self._get(f"/content/{page_id}", params={'expand': 'body.storage,version,space'})
        title = page.get('title', 'Untitled')
        html = (
            page.get('body', {})
            .get('storage', {})
            .get('value', '')
        )
        md = html_to_markdown(html)
        last_updated = (page.get('version') or {}).get('when')
        return WikiContent(id=str(page_id), title=title, markdown=md, source_url=self.base_url + f"/pages/{page_id}", last_updated=last_updated)

    def upsert_content(self, identifier: dict, content: WikiContent) -> Tuple[dict, bool]:
        page_id = identifier.get('page_id')
        title = identifier.get('title') or content.title or 'Untitled'
        space_key = identifier.get('space_key')
        parent_id = identifier.get('parent_id')
        html = markdown_to_html(content.markdown or '')
        if page_id:
            # Update existing page: need current version
            existing = self._get(f"/content/{page_id}", params={'expand': 'version'})
            current_version = (existing.get('version') or {}).get('number', 1)
            payload = {
                'id': str(page_id),
                'type': 'page',
                'title': title or existing.get('title', 'Untitled'),
                'version': {'number': current_version + 1},
                'body': {'storage': {'value': html, 'representation': 'storage'}},
            }
            updated = self._put(f"/content/{page_id}", json=payload)
            return ({'page_id': updated.get('id')}, False)
        else:
            if not space_key:
                raise WikiAdapterError("Confluence create requires 'space_key' when 'page_id' is not provided")
            payload = {
                'type': 'page',
                'title': title,
                'space': {'key': space_key},
                'body': {'storage': {'value': html, 'representation': 'storage'}},
            }
            if parent_id:
                payload['ancestors'] = [{'id': str(parent_id)}]
            created = self._post('/content', json=payload)
            return ({'page_id': created.get('id')}, True)

