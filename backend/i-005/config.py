import os


class Config:
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))  # 10MB
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = os.getenv('DATA_DIR', os.path.join(BASE_DIR, 'data'))
    REDACTED_DIR = os.getenv('REDACTED_DIR', os.path.join(DATA_DIR, 'redacted'))
    LOG_DIR = os.getenv('LOG_DIR', os.path.join(DATA_DIR, 'logs'))

