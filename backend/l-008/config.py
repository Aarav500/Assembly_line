import os

DATA_DIR = os.getenv("DATA_DIR", "data")
DOCS_PATH = os.path.join(DATA_DIR, "docs.jsonl")
TFIDF_PATH = os.path.join(DATA_DIR, "tfidf.pkl")
EMB_PATH = os.path.join(DATA_DIR, "embeddings.npy")
META_PATH = os.path.join(DATA_DIR, "meta.json")

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
DISABLE_EMBEDDINGS = os.getenv("DISABLE_EMBEDDINGS", "0") in ("1", "true", "True")

MAX_DOC_LENGTH = int(os.getenv("MAX_DOC_LENGTH", "200000"))  # characters
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", "2000000"))  # 2 MB

# Lexical vectorizer settings
NGRAM_RANGE = (1, 2)
MIN_DF = 1
MAX_FEATURES = None
STOP_WORDS = None

