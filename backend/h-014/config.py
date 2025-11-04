import os

# Directories and files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')
INDEX_FILE = os.path.join(DATA_DIR, 'index.joblib')
FAQ_FILE = os.path.join(DATA_DIR, 'faq.json')

# Limits
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB per file
MAX_DOC_CHARS = 8000
MAX_FAQS = 30
MAX_FAQ_ANSWER_CHARS = 1200
MAX_FUNCTION_FAQS = 12

# File types
DOC_EXTENSIONS = {
    '.md', '.markdown', '.rst', '.txt'
}
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go', '.rb', '.php', '.rs', '.swift', '.kt',
    '.c', '.h', '.hpp', '.cpp', '.cc', '.m', '.mm', '.sh', '.bash', '.zsh', '.ps1', '.scala', '.sql', '.lua', '.r', '.yml', '.yaml'
}

# Ignore directories when indexing
IGNORE_DIRS = {
    'node_modules', '.git', '.hg', '.svn', '.idea', '.vscode', '__pycache__', '.pytest_cache',
    '.venv', 'venv', 'env', 'build', 'dist', '.cache', 'coverage', '.mypy_cache'
}

