import os

class Config:
    def __init__(self):
        self.BUILD_ROOT = os.getenv("BUILD_ROOT", os.path.abspath(os.path.join(os.getcwd(), "builds")))
        self.DATA_DIR = os.getenv("DATA_DIR", os.path.abspath(os.path.join(os.getcwd(), "data")))
        self.CDN_PROVIDER = os.getenv("CDN_PROVIDER", "noop").lower()
        self.CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")  # e.g. https://www.example.com
        self.CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
        self.CF_ZONE_ID = os.getenv("CF_ZONE_ID", "")
        self.FASTLY_API_KEY = os.getenv("FASTLY_API_KEY", "")
        self.FASTLY_SERVICE_ID = os.getenv("FASTLY_SERVICE_ID", "")
        self.JOB_WORKERS = int(os.getenv("JOB_WORKERS", "1"))
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    def ensure_dirs(self):
        os.makedirs(self.BUILD_ROOT, exist_ok=True)
        os.makedirs(self.DATA_DIR, exist_ok=True)

config = Config()
config.ensure_dirs()

