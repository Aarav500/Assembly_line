import base64
import json

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    # Add padding back if missing
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def canonicalize_json_obj(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")

