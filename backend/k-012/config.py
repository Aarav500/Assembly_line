import os
from secrets import token_urlsafe

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///tenants.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv("SECRET_KEY", token_urlsafe(32))
    JSON_SORT_KEYS = False


