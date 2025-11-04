import os
from datetime import datetime


class Config:
    API_VENDOR = os.getenv("API_VENDOR", "example")
    DEFAULT_API_VERSION = os.getenv("DEFAULT_API_VERSION", "v2")
    SUPPORTED_VERSIONS = ["v1", "v2"]

    # Deprecation metadata for backward compatibility strategies
    # See RFC 8594 for Sunset header; Deprecation header is de-facto
    DEPRECATIONS = {
        "v1": {
            "sunset": os.getenv("V1_SUNSET", "2026-01-01"),
            "link": os.getenv("V1_DEPRECATION_LINK", "https://example.com/docs/deprecations/v1"),
            "note": os.getenv("V1_DEPRECATION_NOTE", "API v1 is deprecated; migrate to v2")
        }
    }

    # Toggle response envelope if desired
    RESPONSE_ENVELOPE = False

    # Basic in-memory data seed for demo purposes
    SEED_USERS = [
        {"id": 1, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
        {"id": 2, "first_name": "Alan", "last_name": "Turing", "email": "alan@example.com"}
    ]

    @staticmethod
    def sunset_http_date(version: str | None) -> str | None:
        if not version:
            return None
        meta = Config.DEPRECATIONS.get(version)
        if not meta:
            return None
        try:
            # Return as IMF-fixdate for header if a full datetime is provided; else just date
            dt = datetime.fromisoformat(meta["sunset"])  # may be date-only
            return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        except Exception:
            return meta["sunset"]

