import os
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    NoEncryption,
    PublicFormat,
    load_pem_private_key,
)


def ensure_keypair(private_key_path: str):
    if os.path.exists(private_key_path):
        return
    os.makedirs(os.path.dirname(private_key_path), exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    pem = priv.private_bytes(encoding=Encoding.PEM, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption())
    with open(private_key_path, "wb") as f:
        f.write(pem)


def load_private_key(private_key_path: str) -> Ed25519PrivateKey:
    with open(private_key_path, "rb") as f:
        data = f.read()
    key = load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("private key must be ed25519")
    return key


def load_public_key(private_key_path: str) -> Ed25519PublicKey:
    priv = load_private_key(private_key_path)
    return priv.public_key()


def load_public_key_bytes(private_key_path: str) -> bytes:
    pub = load_public_key(private_key_path)
    return pub.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)


def keyid_from_public(public_key_bytes: bytes) -> str:
    return hashlib.sha256(public_key_bytes).hexdigest()

