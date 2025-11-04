import hashlib
import hmac
import os


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256(); h.update(b); return h.hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def hmac_sha256(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def redact_email(email: str) -> str:
    if not email or '@' not in email:
        return 'redacted'
    name, domain = email.split('@', 1)
    masked = (name[0] + '***') if name else '***'
    dparts = domain.split('.')
    dmasked = dparts[0][0] + '***' if dparts and dparts[0] else '***'
    tld = dparts[-1] if len(dparts) > 1 else '***'
    return f"{masked}@{dmasked}.{tld}"


def pseudonym(value: str) -> str:
    if not value:
        return 'anon'
    # stable pseudonym based on SHA256 digest
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]
    return f"user_{digest}"

