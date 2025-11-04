from __future__ import annotations
from typing import Iterable, Optional

import meilisearch

from . import BaseSearchClient


class MeilisearchClient(BaseSearchClient):
    def __init__(self, url: str, api_key: str | None = None, default_settings: dict | None = None) -> None:
        self.client = meilisearch.Client(url, api_key or "")
        self.default_settings = default_settings or {}

    def _ensure_index(self, index: str) -> meilisearch.index.Index:
        try:
            return self.client.get_index(index)
        except meilisearch.errors.MeiliSearchApiError:
            # Create if not exists, set primary key to 'id'
            idx = self.client.create_index(index, {"primaryKey": "id"})
            # Apply default settings if provided
            if self.default_settings:
                idx.update_settings(self.default_settings)
            return idx

    def create_index(self, index: str, schema: dict | None = None) -> dict:
        try:
            idx = self.client.get_index(index)
            return {"acknowledged": True, "message": "exists"}
        except meilisearch.errors.MeiliSearchApiError:
            idx = self.client.create_index(index, {"primaryKey": "id"})
            if self.default_settings:
                idx.update_settings(self.default_settings)
            return {"acknowledged": True, "message": "created"}

    def delete_index(self, index: str) -> dict:
        try:
            task = self.client.index(index).delete()
            return {"acknowledged": True, "taskUid": task.get("taskUid")}
        except meilisearch.errors.MeiliSearchApiError:
            return {"acknowledged": True, "message": "not_found"}

    def index_document(self, index: str, id: str | int, body: dict) -> dict:
        idx = self._ensure_index(index)
        doc = dict(body)
        doc["id"] = id
        task = idx.add_documents([doc])
        return {"enqueued": True, "taskUid": task.get("taskUid")}

    def get_document(self, index: str, id: str | int) -> Optional[dict]:
        try:
            return self.client.index(index).get_document(str(id))
        except meilisearch.errors.MeiliSearchApiError:
            return None

    def bulk_index(self, index: str, docs: Iterable[dict]) -> dict:
        idx = self._ensure_index(index)
        payload = []
        for d in docs:
            doc = dict(d)
            if "id" not in doc:
                continue
            payload.append(doc)
        if not payload:
            return {"enqueued": False, "count": 0}
        task = idx.add_documents(payload)
        return {"enqueued": True, "count": len(payload), "taskUid": task.get("taskUid")}

    def search(self, index: str, query: str, limit: int = 10, offset: int = 0) -> dict:
        idx = self._ensure_index(index)
        res = idx.search(query, {"limit": limit, "offset": offset})
        hits = res.get("hits", [])
        total = res.get("estimatedTotalHits") or res.get("totalHits") or len(hits)
        return {"total": int(total), "limit": limit, "offset": offset, "hits": hits}

    def ping(self) -> bool:
        try:
            h = self.client.health()
            return h.get("status") == "available"
        except Exception:
            return False

