import os
from pathlib import Path

class Config:
    '''Base configuration'''
    try:
        SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration: {e}")

class TestConfig(Config):
    '''Test configuration'''
    try:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
    except Exception as e:
        raise RuntimeError(f"Failed to load test configuration: {e}")

try:
    config = {
        'development': Config,
        'testing': TestConfig,
        'default': Config
    }
except Exception as e:
    raise RuntimeError(f"Failed to create config dictionary: {e}")