import os
from elasticsearch import Elasticsearch

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

_client = None

def get_client() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(ES_URL, request_timeout=30)
    return _client

def ensure_connected():
    es = get_client()
    info = es.info()
    return info

