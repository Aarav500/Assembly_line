import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///audit.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    JSON_LOG_FILE = os.getenv(
        "JSON_LOG_FILE",
        os.path.join(os.getcwd(), "logs", "app.jsonl")
    )
    APP_NAME = os.getenv("APP_NAME", "agent-audit-app")

