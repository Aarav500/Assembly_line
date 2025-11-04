import os
from pathlib import Path
import secrets

class Config:
    '''Base configuration'''
    try:
        SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-please-change-in-production')
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    except Exception as e:
        raise RuntimeError(f"Error loading configuration: {e}")

class TestConfig(Config):
    '''Test configuration'''
    try:
        SECRET_KEY = secrets.token_hex(32)
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
    except Exception as e:
        raise RuntimeError(f"Error loading test configuration: {e}")

try:
    config = {
        'development': Config,
        'testing': TestConfig,
        'default': Config
    }
except Exception as e:
    print(f"Error creating config dictionary: {e}")
    config = {'default': Config}