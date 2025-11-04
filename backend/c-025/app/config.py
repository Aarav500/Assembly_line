import os
from dataclasses import dataclass


@dataclass
class Config:
    # General
    DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")

    # Search backend selection: "elasticsearch" or "meilisearch"
    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "elasticsearch").lower()

    # Elasticsearch settings
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    ELASTICSEARCH_USERNAME: str | None = os.getenv("ELASTICSEARCH_USERNAME")
    ELASTICSEARCH_PASSWORD: str | None = os.getenv("ELASTICSEARCH_PASSWORD")
    ELASTICSEARCH_VERIFY_CERTS: bool = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "1") == "1"
    ELASTICSEARCH_CA_CERTS: str | None = os.getenv("ELASTICSEARCH_CA_CERTS")

    # Meilisearch settings
    MEILISEARCH_URL: str = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
    MEILISEARCH_API_KEY: str | None = os.getenv("MEILISEARCH_API_KEY")

    # App defaults
    DEFAULT_INDEX_NAME: str = os.getenv("DEFAULT_INDEX_NAME", "documents")

