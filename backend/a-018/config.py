import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCANS_DIR = os.path.join(DATA_DIR, "scans")
WORK_DIR = os.path.join(DATA_DIR, "work")

# Limits
try:
    MAX_ARCHIVE_SIZE_BYTES = int(os.environ.get("MAX_ARCHIVE_SIZE_BYTES", 100 * 1024 * 1024))  # 100MB
except (ValueError, TypeError):
    MAX_ARCHIVE_SIZE_BYTES = 100 * 1024 * 1024

try:
    MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_BYTES", 5 * 1024 * 1024))  # 5MB per file
except (ValueError, TypeError):
    MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

try:
    MAX_FILES_TO_SCAN = int(os.environ.get("MAX_FILES_TO_SCAN", 5000))
except (ValueError, TypeError):
    MAX_FILES_TO_SCAN = 5000

# Allow which import methods: set env like "git,zip"
try:
    ALLOWED_IMPORT_METHODS = set([s.strip() for s in os.environ.get("ALLOWED_IMPORT_METHODS", "git,zip").split(',') if s.strip()])
except (AttributeError, TypeError):
    ALLOWED_IMPORT_METHODS = {"git", "zip"}