import os

DATA_DIR = os.environ.get('APP_DATA_DIR', 'data')

SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rb', '.php', '.cs',
    '.c', '.h', '.cpp', '.hpp', '.swift', '.kt', '.css', '.scss', '.html', '.md'
}

IGNORE_DIRS = {
    'node_modules', 'venv', '.venv', '__pycache__', '.git', 'dist', 'build', '.tox', '.mypy_cache', '.pytest_cache', '.idea', '.vscode'
}

SHINGLE_SIZE = 5
NEAR_DUP_THRESHOLD = 0.85
MAX_FILES_FOR_NEAR_DUP = 2500

