import os

class Config:
    FEATURE_FLAG_FILE = os.environ.get(
        "FEATURE_FLAG_FILE", os.path.join(os.getcwd(), "feature_flags.json")
    )
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = os.environ.get("DEBUG", "1") in ("1", "true", "True")

