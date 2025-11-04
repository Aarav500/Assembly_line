import os


class Config:
    def __init__(self):
        self.SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
        self.DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///usage.db")
        self.JSONIFY_PRETTYPRINT_REGULAR = False
        self.PROPAGATE_EXCEPTIONS = True

