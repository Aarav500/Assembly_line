import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))  # 10MB
    ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in os.environ.get('ALLOWED_EXTENSIONS', 'csv,txt').split(',') if ext.strip()}
    PRIVACY_MODE = os.environ.get('PRIVACY_MODE', 'true').lower() in {'1', 'true', 'yes', 'on'}
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'instance', 'uploads')

