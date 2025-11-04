import os

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DATASETS_DIR = os.path.join(DATA_DIR, 'datasets')
    PROFILES_DIR = os.path.join(DATA_DIR, 'profiles')
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024  # 512MB upload limit
    JSON_AS_ASCII = False
    EAGER_PROFILE = True

