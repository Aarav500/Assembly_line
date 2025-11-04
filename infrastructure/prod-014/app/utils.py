from typing import Any

SENSITIVE_KEYS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "private_key",
    "client_secret",
)


def _mask(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) <= 8:
            return "******"
        return value[:2] + "***" + value[-2:]
    return "******"


def sanitize_config(obj: Any) -> Any:
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                clean[k] = _mask(v)
            else:
                clean[k] = sanitize_config(v)
        return clean
    if isinstance(obj, list):
        return [sanitize_config(i) for i in obj]
    return obj

