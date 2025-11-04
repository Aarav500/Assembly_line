import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DEFAULT_TAXONOMY_THRESHOLD = float(os.getenv("DEFAULT_TAXONOMY_THRESHOLD", 1.0))
    MAX_TERMS_PER_DOC = int(os.getenv("MAX_TERMS_PER_DOC", 100))

