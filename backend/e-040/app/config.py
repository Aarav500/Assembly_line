import os

class Config:
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(os.getcwd(), 'instance', 'app.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

