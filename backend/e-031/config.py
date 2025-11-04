import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///data.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'dev-admin-key')

    # rotation
    DEFAULT_ROTATION_INTERVAL_SECONDS = int(os.getenv('DEFAULT_ROTATION_INTERVAL_SECONDS', '86400'))  # 24h
    MIN_ROTATION_INTERVAL_SECONDS = int(os.getenv('MIN_ROTATION_INTERVAL_SECONDS', '60'))  # 60s
    ROTATION_CHECK_INTERVAL_SECONDS = int(os.getenv('ROTATION_CHECK_INTERVAL_SECONDS', '30'))  # poll every 30s
    ROTATION_CHECK_JITTER_SECONDS = int(os.getenv('ROTATION_CHECK_JITTER_SECONDS', '5'))

    # audit
    AUDIT_LOG_FILE = os.getenv('AUDIT_LOG_FILE', 'logs/audit.log')

    # Flask secret
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

