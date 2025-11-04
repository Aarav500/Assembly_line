import json
import os
from typing import Tuple

from adapters.base import WikiAdapterError
from adapters.notion_adapter import NotionAdapter
from adapters.confluence_adapter import ConfluenceAdapter
from adapters.filesystem_adapter import FilesystemAdapter
from models.wiki_content import WikiContent
from config import Config

class SyncError(Exception):
    def __init__(self, message: str, status: int = 400, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.details = details or {}

class MappingStore:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump({"mappings": {}}, f)
        self._data = self._load()

    def _load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def dump(self):
        return self._data

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=2)

    def _key(self, provider: str, identity: dict) -> str:
        # identity should be stable string
        if provider == 'confluence':
            if 'page_id' in identity:
                return f"confluence:page_id:{identity['page_id']}"
            elif 'space_key' in identity and 'title' in identity:
                return f"confluence:space:{identity['space_key']}:title:{identity['title']}"
        elif provider == 'notion':
            if 'page_id' in identity:
                return f"notion:page_id:{identity['page_id']}"
        elif provider == 'files':
            if 'path' in identity:
                return f"files:path:{identity['path']}"
            elif 'title' in identity:
                return f"files:title:{identity['title']}"
        return f"{provider}:{json.dumps(identity, sort_keys=True)}"

    def set_mapping(self, src_provider: str, src_identity: dict, tgt_provider: str, tgt_identity: dict):
        s = self._key(src_provider, src_identity)
        t = self._key(tgt_provider, tgt_identity)
        self._data.setdefault('mappings', {})[s] = t
        self._data['mappings'][t] = s
        self.save()

class SyncService:
    def __init__(self, config: Config):
        self.config = config
        self.mapping_store = MappingStore(config.mappings_file)

    def _adapter(self, provider: str):
        p = provider.lower()
        if p == 'notion':
            return NotionAdapter(self.config.notion_token, self.config.notion_version)
        if p == 'confluence':
            return ConfluenceAdapter(self.config.confluence_base_url, self.config.confluence_username, self.config.confluence_api_token)
        if p == 'files':
            return FilesystemAdapter(self.config.file_wiki_dir)
        raise SyncError(f"Unsupported provider: {provider}", status=400)

    def _read_source(self, src: dict) -> Tuple[WikiContent, dict]:
        provider = src.get('provider')
        if not provider:
            raise SyncError("source.provider is required", 400)
        adapter = self._adapter(provider)
        identity = {k: v for k, v in src.items() if k != 'provider'}
        try:
            content = adapter.get_content(identity)
            return content, identity
        except WikiAdapterError as e:
            raise SyncError(str(e), status=400, details=e.details)

    def _write_target(self, tgt: dict, content: WikiContent) -> Tuple[dict, bool]:
        provider = tgt.get('provider')
        if not provider:
            raise SyncError("target.provider is required", 400)
        adapter = self._adapter(provider)
        identity = {k: v for k, v in tgt.items() if k != 'provider'}
        try:
            resolved, created = adapter.upsert_content(identity, content)
            return resolved, created
        except WikiAdapterError as e:
            raise SyncError(str(e), status=400, details=e.details)

    def sync(self, payload: dict) -> dict:
        source = payload.get('source')
        target = payload.get('target')
        options = payload.get('options', {})
        if not source or not target:
            raise SyncError("'source' and 'target' are required", 400)

        content, src_identity = self._read_source(source)
        # allow overriding title on target
        override_title = target.get('title') or options.get('title')
        if override_title:
            content.title = override_title
        result_identity, created = self._write_target(target, content)

        # store mapping
        self.mapping_store.set_mapping(source['provider'], src_identity, target['provider'], result_identity)

        return {
            'status': 'ok',
            'action': 'created' if created else 'updated',
            'source': {
                'provider': source['provider'],
                'identity': src_identity,
                'title': content.title,
            },
            'target': {
                'provider': target['provider'],
                'identity': result_identity,
                'created': created,
            }
        }

