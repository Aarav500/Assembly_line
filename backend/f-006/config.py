import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JSON_SORT_KEYS = False


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

