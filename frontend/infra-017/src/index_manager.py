from typing import Iterable, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

DEFAULT_SETTINGS = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "analysis": {
            "filter": {
                "english_stop": {"type": "stop", "stopwords": "_english_"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "my_synonyms": {
                    "type": "synonym_graph",
                    "synonyms_path": "synonyms/synonyms.txt",
                    "updateable": True
                }
            },
            "tokenizer": {
                "autocomplete_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"]
                }
            },
            "analyzer": {
                "text_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "asciifolding",
                        "english_stop",
                        "english_stemmer",
                        "my_synonyms"
                    ]
                },
                "autocomplete_analyzer": {
                    "type": "custom",
                    "tokenizer": "autocomplete_tokenizer",
                    "filter": ["lowercase", "asciifolding"]
                },
                "autocomplete_search_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"]
                }
            }
        }
    },
    "mappings": {
        "dynamic": True,
        "dynamic_templates": [
            {
                "attributes_keywords": {
                    "path_match": "attributes.*",
                    "match_mapping_type": "string",
                    "mapping": {"type": "keyword"}
                }
            }
        ],
        "properties": {
            "title": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {
                    "keyword": {"type": "keyword", "ignore_above": 256},
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete_analyzer",
                        "search_analyzer": "autocomplete_search_analyzer"
                    }
                }
            },
            "title_suggest": {"type": "completion", "preserve_separators": True},
            "description": {"type": "text", "analyzer": "text_analyzer"},
            "category": {"type": "keyword"},
            "brand": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "price": {"type": "float"},
            "created_at": {"type": "date"},
            "attributes": {"type": "object", "dynamic": True}
        }
    }
}

def create_index(es: Elasticsearch, index_name: str, settings: Optional[dict] = None) -> dict:
    if es.indices.exists(index=index_name):
        return {"acknowledged": True, "message": "Index already exists"}
    body = settings or DEFAULT_SETTINGS
    return es.indices.create(index=index_name, **body)

def delete_index(es: Elasticsearch, index_name: str) -> dict:
    if not es.indices.exists(index=index_name):
        return {"acknowledged": True, "message": "Index did not exist"}
    return es.indices.delete(index=index_name)

def reset_index(es: Elasticsearch, index_name: str, settings: Optional[dict] = None) -> dict:
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
    return es.indices.create(index=index_name, **(settings or DEFAULT_SETTINGS))

def upsert_document(es: Elasticsearch, index_name: str, doc_id: Optional[str], source: dict, refresh: bool = True) -> dict:
    # Populate completion field if not present
    if "title" in source and "title_suggest" not in source:
        source["title_suggest"] = source["title"]
    return es.index(index=index_name, id=doc_id, document=source, refresh="wait_for" if refresh else False)

def bulk_index(es: Elasticsearch, index_name: str, docs: Iterable[dict], refresh: bool = True) -> dict:
    def actions():
        for d in docs:
            src = dict(d)
            if "title" in src and "title_suggest" not in src:
                src["title_suggest"] = src["title"]
            _id = src.pop("id", None)
            yield {"_op_type": "index", "_index": index_name, "_id": _id, "_source": src}
    success, errors = bulk(es, actions())
    if refresh:
        es.indices.refresh(index=index_name)
    return {"items_indexed": success, "errors": errors}

def reload_search_analyzers(es: Elasticsearch, index_name: str) -> dict:
    return es.indices.reload_search_analyzers(index=index_name)

