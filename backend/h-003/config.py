import os
from pathlib import Path


class AppConfig:
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

    DEFAULT_STORE = os.getenv("VECTOR_STORE", "chroma").lower()
    AVAILABLE_STORES = [s.strip() for s in os.getenv("AVAILABLE_STORES", "chroma,pgvector").split(",") if s.strip()]

    DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "default")

    # Chroma
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(Path("data/chroma").absolute()))

    # Postgres/pgvector
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = int(os.getenv("PG_PORT", "5432"))
    PG_DATABASE = os.getenv("PG_DATABASE", "vectordb")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
    PG_SCHEMA = os.getenv("PG_SCHEMA", "public")
    PG_INDEX_LISTS = int(os.getenv("PG_INDEX_LISTS", "100"))
    PG_CREATE_EXTENSION = os.getenv("PG_CREATE_EXTENSION", "1") == "1"

    # Ensure directories exist
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

