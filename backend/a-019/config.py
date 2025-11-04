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
        print(f"Error loading configuration: {e}")
        SECRET_KEY = 'dev-secret-key'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = True

class TestConfig(Config):
    '''Test configuration'''
    try:
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