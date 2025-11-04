import os

# Directory containing documentation files to index
docs_glob = os.getenv("DOCS_GLOB", "docs/**/*.*")
# File patterns to include (by extension)
include_exts = {ext.strip().lower() for ext in os.getenv("DOCS_INCLUDE_EXTS", ".md,.txt,.rst").split(",")}
# Maximum characters per chunk
chunk_max_chars = int(os.getenv("CHUNK_MAX_CHARS", "800"))
# Chunk overlap in characters
chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "80"))
# Number of top contexts to return by default
default_top_k = int(os.getenv("DEFAULT_TOP_K", "3"))
# Path to tests file
qa_tests_path = os.getenv("QA_TESTS_PATH", "tests/qa_tests.yaml")

