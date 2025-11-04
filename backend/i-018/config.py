import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


def bool_from_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data.db")
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
    GITHUB_WEBHOOK_SECRET: Optional[str] = os.getenv("GITHUB_WEBHOOK_SECRET")

    # Policy
    REQUIRE_SIGNED_COMMITS: bool = bool_from_env("REQUIRE_SIGNED_COMMITS", True)
    REQUIRE_DCO: bool = bool_from_env("REQUIRE_DCO", False)
    ALLOWED_SIGNATURE_KEY_IDS: List[str] = field(default_factory=list)
    ALLOWED_SIGNER_USERNAMES: List[str] = field(default_factory=list)
    ALLOWED_SIGNER_EMAILS: List[str] = field(default_factory=list)

    # Status context and dashboard link
    STATUS_CONTEXT: str = os.getenv("STATUS_CONTEXT", "provenance-policy")
    DASHBOARD_BASE_URL: Optional[str] = os.getenv("DASHBOARD_BASE_URL")

    def __post_init__(self):
        if os.getenv("ALLOWED_SIGNATURE_KEY_IDS"):
            try:
                self.ALLOWED_SIGNATURE_KEY_IDS = json.loads(os.getenv("ALLOWED_SIGNATURE_KEY_IDS"))
            except Exception:
                self.ALLOWED_SIGNATURE_KEY_IDS = [x.strip() for x in os.getenv("ALLOWED_SIGNATURE_KEY_IDS").split(",") if x.strip()]
        if os.getenv("ALLOWED_SIGNER_USERNAMES"):
            try:
                self.ALLOWED_SIGNER_USERNAMES = json.loads(os.getenv("ALLOWED_SIGNER_USERNAMES"))
            except Exception:
                self.ALLOWED_SIGNER_USERNAMES = [x.strip() for x in os.getenv("ALLOWED_SIGNER_USERNAMES").split(",") if x.strip()]
        if os.getenv("ALLOWED_SIGNER_EMAILS"):
            try:
                self.ALLOWED_SIGNER_EMAILS = json.loads(os.getenv("ALLOWED_SIGNER_EMAILS"))
            except Exception:
                self.ALLOWED_SIGNER_EMAILS = [x.strip() for x in os.getenv("ALLOWED_SIGNER_EMAILS").split(",") if x.strip()]


settings = Settings()

