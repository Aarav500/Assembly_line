import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///ledger.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    PROPAGATE_EXCEPTIONS = True
    PREFERRED_URL_SCHEME = "https"
    TIMEZONE = os.getenv("TIMEZONE", "UTC")

