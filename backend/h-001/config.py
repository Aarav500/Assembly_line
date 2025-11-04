import os

class Config:
    DEBUG = os.getenv('DEBUG', 'false').lower() in ('1', 'true', 'yes')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    DATA_DIR = os.getenv('DATA_DIR', os.path.join(os.getcwd(), 'data'))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(DATA_DIR, 'uploads'))
    REPO_FOLDER = os.getenv('REPO_FOLDER', os.path.join(DATA_DIR, 'repos'))

    SQLALCHEMY_DATABASE_PATH = os.getenv('DB_PATH', os.path.join(DATA_DIR, 'app.db'))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{SQLALCHEMY_DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH_MB', '50')) * 1024 * 1024

    ALLOWED_EXTENSIONS = set((
        # documents
        'pdf', 'docx', 'txt', 'md',
        # data/config
        'json', 'yaml', 'yml', 'toml',
        # code & markup
        'py', 'js', 'ts', 'java', 'go', 'rb', 'php', 'cpp', 'c', 'cs', 'rs', 'html', 'css', 'sh', 'sql'
    ))

