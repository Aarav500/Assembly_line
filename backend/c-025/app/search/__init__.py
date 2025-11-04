from __future__ import annotations
from typing import Any, Iterable, Optional


class BaseSearchClient:
    def create_index(self, index: str, schema: Optional[dict] = None) -> dict:
        raise NotImplementedError

    def delete_index(self, index: str) -> dict:
        raise NotImplementedError

    def index_document(self, index: str, id: str | int, body: dict) -> dict:
        raise NotImplementedError

    def get_document(self, index: str, id: str | int) -> Optional[dict]:
        raise NotImplementedError

    def bulk_index(self, index: str, docs: Iterable[dict]) -> dict:
        raise NotImplementedError

    def search(self, index: str, query: str, limit: int = 10, offset: int = 0) -> dict:
        raise NotImplementedError

    def ping(self) -> bool:
        raise NotImplementedError


DEFAULT_ES_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "content": {"type": "text", "analyzer": "standard"},
            "tags": {"type": "keyword"},
            "created_at": {"type": "date", "format": "strict_date_optional_time||epoch_millis"},
        }
    }
}

DEFAULT_MEILI_SETTINGS = {
    "searchableAttributes": ["title", "content", "tags"],
    "filterableAttributes": ["tags"],
    "sortableAttributes": ["created_at"],
}


def create_search_client(config) -> BaseSearchClient:
    backend = (getattr(config, "SEARCH_BACKEND", "elasticsearch") or "").lower()
    if backend not in {"elasticsearch", "meilisearch"}:
        raise ValueError(f"Unsupported SEARCH_BACKEND: {backend}")

    if backend == "elasticsearch":
        try:
            from .elasticsearch_backend import ElasticsearchSearchClient
        except Exception as e:
            raise RuntimeError("Elasticsearch client not available. Install 'elasticsearch' package.") from e
        return ElasticsearchSearchClient(
            url=config.ELASTICSEARCH_URL,
            username=config.ELASTICSEARCH_USERNAME,
            password=config.ELASTICSEARCH_PASSWORD,
            verify_certs=config.ELASTICSEARCH_VERIFY_CERTS,
            ca_certs=config.ELASTICSEARCH_CA_CERTS,
            default_mapping=DEFAULT_ES_MAPPING,
        )

    else:  # meilisearch
        try:
            from .meilisearch_backend import MeilisearchClient
        except Exception as e:
            raise RuntimeError("Meilisearch client not available. Install 'meilisearch' package.") from e
        return MeilisearchClient(
            url=config.MEILISEARCH_URL,
            api_key=config.MEILISEARCH_API_KEY,
            default_settings=DEFAULT_MEILI_SETTINGS,
        )

