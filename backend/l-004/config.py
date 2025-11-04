import os
from datetime import date

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme-admin-token")
    DEFAULT_BILLING_ANCHOR = date.today()

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

