import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///catalog.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 100 * 1024 * 1024))
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.abspath(os.path.join(os.getcwd(), "data", "uploads")))

