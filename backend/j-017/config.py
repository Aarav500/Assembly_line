import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AI Provider config
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")  # auto | openai | echo
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "300"))

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

