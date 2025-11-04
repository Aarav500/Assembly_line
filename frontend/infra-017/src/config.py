import os
from functools import lru_cache
from elasticsearch import Elasticsearch

INDEX_NAME = os.getenv("INDEX_NAME", "products")

@lru_cache(maxsize=1)
def get_es_client() -> Elasticsearch:
    host = os.getenv("ELASTIC_HOST", "http://localhost:9200")
    api_key = os.getenv("ELASTIC_API_KEY")
    username = os.getenv("ELASTIC_USER")
    password = os.getenv("ELASTIC_PASSWORD")
    ca_certs = os.getenv("ELASTIC_CA_CERT")

    kwargs = {"hosts": [host]}

    if api_key:
        kwargs["api_key"] = api_key
    elif username and password:
        kwargs["basic_auth"] = (username, password)

    if ca_certs:
        kwargs["ca_certs"] = ca_certs

    # For HTTP (no TLS), ignore SSL config
    return Elasticsearch(**kwargs)

