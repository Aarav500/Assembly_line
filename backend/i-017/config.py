import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///privacy_scaffold.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Data retention
    DATA_RETENTION_DAYS = int(os.getenv('DATA_RETENTION_DAYS', '30'))
    START_RETENTION_WORKER = os.getenv('START_RETENTION_WORKER', 'true').lower() == 'true'

    # Admin key for privileged operations
    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY')

    # App secret
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', os.urandom(24))\

