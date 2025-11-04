from typing import Dict, Any
from elasticsearch import Elasticsearch

PRODUCTS_INDEX_DEFAULT = "products"
ANALYTICS_INDEX_DEFAULT = "search-analytics"


def products_index_settings(index_name: str = PRODUCTS_INDEX_DEFAULT) -> Dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "filter": {
                    "autocomplete_filter": {
                        "type": "edge_ngram",
                        "min_gram": 1,
                        "max_gram": 20
                    },
                    "english_stop": {
                        "type": "stop",
                        "stopwords": "_english_"
                    },
                    "english_stemmer": {
                        "type": "stemmer",
                        "language": "english"
                    },
                    "english_possessive_stemmer": {
                        "type": "stemmer",
                        "language": "possessive_english"
                    },
                    "synonyms_filter": {
                        "type": "synonym",
                        "synonyms": [
                            "tv, television",
                            "cellphone, mobile, smartphone",
                            "notebook, laptop",
                            "headphone, headset"
                        ]
                    }
                },
                "normalizer": {
                    "lowercase_normalizer": {
                        "type": "custom",
                        "filter": ["lowercase", "asciifolding"]
                    }
                },
                "analyzer": {
                    "text_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "asciifolding",
                            "english_possessive_stemmer",
                            "english_stop",
                            "english_stemmer",
                            "synonyms_filter"
                        ]
                    },
                    "autocomplete_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "autocomplete_filter"]
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
            "dynamic": "false",
            "properties": {
                "id": {"type": "keyword"},
                "name": {
                    "type": "text",
                    "analyzer": "text_analyzer",
                    "fields": {
                        "keyword": {"type": "keyword", "normalizer": "lowercase_normalizer"},
                        "autocomplete": {
                            "type": "text",
                            "analyzer": "autocomplete_analyzer",
                            "search_analyzer": "autocomplete_search_analyzer"
                        }
                    }
                },
                "name_suggest": {
                    "type": "completion",
                    "contexts": [
                        {"name": "brand", "type": "category", "path": "brand"},
                        {"name": "category", "type": "category", "path": "category"}
                    ]
                },
                "description": {"type": "text", "analyzer": "text_analyzer"},
                "brand": {"type": "keyword", "normalizer": "lowercase_normalizer"},
                "category": {"type": "keyword", "normalizer": "lowercase_normalizer"},
                "price": {"type": "float"},
                "available": {"type": "boolean"},
                "popularity": {"type": "integer"},
                "created_at": {"type": "date"}
            }
        }
    }


def analytics_index_settings(index_name: str = ANALYTICS_INDEX_DEFAULT) -> Dict[str, Any]:
    return {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "dynamic": True,
            "properties": {
                "event_type": {"type": "keyword"},  # 'query' or 'click'
                "timestamp": {"type": "date"},
                "query": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                },
                "filters": {"type": "object", "enabled": True},
                "total_hits": {"type": "integer"},
                "took": {"type": "integer"},
                "index": {"type": "keyword"},
                "user_id": {"type": "keyword"},
                "session_id": {"type": "keyword"},
                "doc_id": {"type": "keyword"},
                "position": {"type": "integer"}
            }
        }
    }


def create_index_if_not_exists(es: Elasticsearch, index_name: str, body: Dict[str, Any]):
    if not es.indices.exists(index=index_name):
        es.indices.create(index=index_name, body=body)


def init_all_indices(es: Elasticsearch, products_index: str = PRODUCTS_INDEX_DEFAULT, analytics_index: str = ANALYTICS_INDEX_DEFAULT):
    create_index_if_not_exists(es, products_index, products_index_settings(products_index))
    create_index_if_not_exists(es, analytics_index, analytics_index_settings(analytics_index))

