import os
from pathlib import Path

class Config:
    '''Base configuration'''
    try:
        SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
        DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    except Exception as e:
        raise RuntimeError(f"Configuration error: {e}")

class TestConfig(Config):
    '''Test configuration'''
    try:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
    except Exception as e:
        raise RuntimeError(f"Test configuration error: {e}")

try:
    config = {
        'development': Config,
        'testing': TestConfig,
        'default': Config
    }
except Exception as e:
    raise RuntimeError(f"Failed to initialize config dictionary: {e}")