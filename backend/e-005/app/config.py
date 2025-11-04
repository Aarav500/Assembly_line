import os


class Config:
    def __init__(self):
        # Flask
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
        # Database
        self.SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///data.db")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        # Registry
        self.REGISTRY_URL = os.getenv("REGISTRY_URL", "").rstrip('/')
        self.REGISTRY_USERNAME = os.getenv("REGISTRY_USERNAME")
        self.REGISTRY_PASSWORD = os.getenv("REGISTRY_PASSWORD")
        self.REGISTRY_VERIFY_SSL = os.getenv("REGISTRY_VERIFY_SSL", "true").lower() == "true"
        # API auth
        self.API_TOKEN = os.getenv("API_TOKEN")
        # Scheduler
        self.SCHEDULE_ENABLED = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"
        self.SCHEDULE_INTERVAL_MINUTES = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", "60"))
        # Defaults
        self.DRY_RUN_DEFAULT = os.getenv("DRY_RUN_DEFAULT", "true").lower() == "true"

