from __future__ import annotations
from typing import Iterable, Optional

from elasticsearch import Elasticsearch, NotFoundError, helpers

from . import BaseSearchClient


class ElasticsearchSearchClient(BaseSearchClient):
    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        verify_certs: bool = True,
        ca_certs: str | None = None,
        default_mapping: dict | None = None,
    ) -> None:
        es_kwargs = {
            "hosts": [url],
            "verify_certs": verify_certs,
        }
        if ca_certs:
            es_kwargs["ca_certs"] = ca_certs
        if username and password:
            es_kwargs["basic_auth"] = (username, password)

        self.client = Elasticsearch(**es_kwargs)
        self.default_mapping = default_mapping or {}

    def create_index(self, index: str, schema: Optional[dict] = None) -> dict:
        if self.client.indices.exists(index=index):
            return {"acknowledged": True, "message": "exists"}
        body = schema or self.default_mapping
        res = self.client.indices.create(index=index, **({"mappings": body.get("mappings", {})} if body else {}))
        return res

    def delete_index(self, index: str) -> dict:
        if not self.client.indices.exists(index=index):
            return {"acknowledged": True, "message": "not_found"}
        return self.client.indices.delete(index=index)

    def index_document(self, index: str, id: str | int, body: dict) -> dict:
        res = self.client.index(index=index, id=str(id), document=body, refresh=True)
        return {"result": res.get("result", "updated"), "_id": res.get("_id")}

    def get_document(self, index: str, id: str | int) -> Optional[dict]:
        try:
            res = self.client.get(index=index, id=str(id))
            src = res.get("_source")
            if src is None:
                return None
            out = dict(src)
            out["id"] = res.get("_id", src.get("id"))
            return out
        except NotFoundError:
            return None

    def bulk_index(self, index: str, docs: Iterable[dict]) -> dict:
        actions = []
        count = 0
        for d in docs:
            doc = dict(d)
            doc_id = str(doc.get("id")) if doc.get("id") is not None else None
            action = {
                "_op_type": "index",
                "_index": index,
                "_source": doc,
            }
            if doc_id:
                action["_id"] = doc_id
            actions.append(action)
        if not actions:
            return {"errors": False, "items": [], "count": 0}
        success, errors = helpers.bulk(self.client, actions, refresh=True, raise_on_error=False)
        return {"errors": bool(errors), "count": success, "items": errors}

    def search(self, index: str, query: str, limit: int = 10, offset: int = 0) -> dict:
        es_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "tags"],
                }
            },
            "from": offset,
            "size": limit,
        }
        res = self.client.search(index=index, body=es_query)
        hits = res.get("hits", {})
        total_val = hits.get("total", {}).get("value") if isinstance(hits.get("total"), dict) else hits.get("total")
        items = []
        for h in hits.get("hits", []):
            src = h.get("_source", {})
            doc = dict(src)
            doc["id"] = h.get("_id", src.get("id"))
            doc["_score"] = h.get("_score")
            items.append(doc)
        return {
            "total": int(total_val or 0),
            "limit": limit,
            "offset": offset,
            "hits": items,
        }

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except Exception:
            return False

