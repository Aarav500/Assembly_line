import os
from dotenv import load_dotenv

load_dotenv()


def _parse_allowed_targets(val: str):
    items = []
    if not val:
        return items
    for part in val.split(","):
        p = part.strip()
        if p:
            items.append(p.lower())
    return items


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(16).hex())
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    API_KEY = os.environ.get("API_KEY")
    WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")

    ALLOWED_TARGETS = _parse_allowed_targets(os.environ.get("ALLOWED_TARGETS", ""))

    ZAP_API_URL = os.environ.get("ZAP_API_URL")
    ZAP_API_KEY = os.environ.get("ZAP_API_KEY")
    ZAP_CONTEXT_NAME = os.environ.get("ZAP_CONTEXT_NAME")

    SCAN_POLL_INTERVAL = int(os.environ.get("SCAN_POLL_INTERVAL", "5"))
    SCAN_MAX_DURATION = int(os.environ.get("SCAN_MAX_DURATION", "900"))

    REPORT_STORAGE_PATH = os.environ.get("REPORT_STORAGE_PATH", "reports")

