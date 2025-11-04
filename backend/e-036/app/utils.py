import os
from typing import Optional
from cryptography import x509
from cryptography.hazmat.primitives import serialization


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_file(path: str, content: bytes, mode: int = 0o600) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as f:
        f.write(content)
    os.chmod(path, mode)


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def cert_not_after_from_pem(pem: bytes) -> Optional[str]:
    try:
        cert = x509.load_pem_x509_certificate(pem)
        return cert.not_valid_after.replace(tzinfo=None).isoformat()
    except Exception:  # noqa: BLE001
        return None


def sanitize_domain_folder(name: str) -> str:
    return name.replace("*", "wildcard").replace("/", "_")

