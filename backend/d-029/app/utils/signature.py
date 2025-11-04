import hmac
import hashlib


def verify_github_signature(secret: str, raw_body: bytes, signature_header: str) -> bool:
    # signature_header format: sha256=...
    try:
        algo, signature = signature_header.split("=", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    # compare using hmac compare_digest
    return hmac.compare_digest(expected, signature)

