import os


class BaseConfig:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Environment gating
    APP_ENV = os.environ.get('APP_ENV', 'development')
    # If true, allow even if not staging (useful for local dev/testing)
    ALLOW_DEMO_DATA = os.environ.get('ALLOW_DEMO_DATA', 'false').lower() in ('1', 'true', 'yes')

    # Optional token to protect the endpoint in staging
    DEMO_DATA_TOKEN = os.environ.get('DEMO_DATA_TOKEN')

