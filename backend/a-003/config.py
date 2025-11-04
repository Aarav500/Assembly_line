import os
from pathlib import Path
import secrets

class Config:
    '''Base configuration'''
    try:
        SECRET_KEY = os.environ['SECRET_KEY']
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    except KeyError:
        raise RuntimeError("SECRET_KEY environment variable must be set")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        raise

class TestConfig(Config):
    '''Test configuration'''
    try:
        SECRET_KEY = secrets.token_hex(32)
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
    except Exception as e:
        print(f"Error loading test configuration: {e}")
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False

config = {
    'development': Config,
    'testing': TestConfig,
    'default': Config
}