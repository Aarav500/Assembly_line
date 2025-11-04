import os
from pathlib import Path

class Config:
    '''Base configuration'''
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    try:
        DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    except Exception as e:
        print(f"Error setting database URI: {e}")
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    try:
        DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    except Exception as e:
        print(f"Error parsing DEBUG setting: {e}")
        DEBUG = True

class TestConfig(Config):
    '''Test configuration'''
    TESTING = True
    
    try:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    except Exception as e:
        print(f"Error setting test database URI: {e}")
        SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    
    WTF_CSRF_ENABLED = False

try:
    config = {
        'development': Config,
        'testing': TestConfig,
        'default': Config
    }
except Exception as e:
    print(f"Error creating config dictionary: {e}")
    config = {'default': Config}