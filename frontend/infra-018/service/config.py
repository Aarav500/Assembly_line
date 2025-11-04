import os


class Config:
    def __init__(self):
        self.SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-me")
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://analytics:analytics@localhost:5432/analytics",
        )
        self.DEBUG = os.getenv("FLASK_ENV") == "development"
        self.JSON_SORT_KEYS = False

