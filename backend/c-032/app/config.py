import base64
import os
from dataclasses import dataclass


def _b64key_or_generate(value: str | None) -> bytes:
    if value:
        try:
            key = base64.urlsafe_b64decode(value)
            # Fernet keys are 32 raw bytes, encoded to 44 urlsafe base64 chars
            if len(key) != 32:
                raise ValueError("Invalid key length")
            return base64.urlsafe_b64encode(key)
        except Exception:
            # If user provided a fernet-formatted key (44 chars), keep as-is
            try:
                base64.urlsafe_b64decode(value)
                return value.encode()
            except Exception as e:  # noqa: F841
                pass
    # Generate ephemeral key (dev fallback)
    from cryptography.fernet import Fernet

    return Fernet.generate_key()


@dataclass
class Config:
    ADMIN_TOKEN: str = os.getenv("APP_ADMIN_TOKEN", "change-me-admin-token")
    SECRETS_DB_PATH: str = os.getenv("SECRETS_DB_PATH", os.path.join(os.getcwd(), "data", "secrets.json"))
    SECRETBOX_KEY: bytes = _b64key_or_generate(os.getenv("SECRETBOX_KEY"))
    SECRET_CACHE_TTL_SECONDS: int = int(os.getenv("SECRET_CACHE_TTL_SECONDS", "60"))
    MAX_KNOWN_SECRETS_FOR_REDACTOR: int = int(os.getenv("MAX_KNOWN_SECRETS_FOR_REDACTOR", "1000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    JSONIFY_PRETTYPRINT_REGULAR: bool = bool(int(os.getenv("JSON_PRETTY", "0")))

