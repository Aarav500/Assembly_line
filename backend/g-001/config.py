import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///registry.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

