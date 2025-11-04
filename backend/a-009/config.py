import os
from pathlib import Path
import logging
import secrets

logger = logging.getLogger(__name__)

class Config:
    '''Base configuration'''
    try:
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            logger.warning("SECRET_KEY not set in environment variables. Generating a random key for this session.")
            secret_key = secrets.token_hex(32)
        SECRET_KEY = secret_key
        SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///app.db')
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    except Exception as e:
        logger.error(f"Error loading base configuration: {e}")
        SECRET_KEY = secrets.token_hex(32)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        DEBUG = True

class TestConfig(Config):
    '''Test configuration'''
    try:
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
        SECRET_KEY = secrets.token_hex(32)
    except Exception as e:
        logger.error(f"Error loading test configuration: {e}")
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        WTF_CSRF_ENABLED = False
        SECRET_KEY = secrets.token_hex(32)

def get_config(config_name='default'):
    '''Get configuration with error handling'''
    try:
        config_map = {
            'development': Config,
            'testing': TestConfig,
            'default': Config
        }
        return config_map.get(config_name, Config)
    except Exception as e:
        logger.error(f"Error getting configuration '{config_name}': {e}")
        return Config

config = {
    'development': Config,
    'testing': TestConfig,
    'default': Config
}