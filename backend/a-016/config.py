import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Config:
    '''Base configuration'''
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

class TestConfig(Config):
    '''Test configuration'''
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

def get_config(config_name='default'):
    '''Get configuration with error handling'''
    try:
        config_dict = {
            'development': Config,
            'testing': TestConfig,
            'default': Config
        }
        return config_dict.get(config_name, Config)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return Config

config = {
    'development': Config,
    'testing': TestConfig,
    'default': Config
}