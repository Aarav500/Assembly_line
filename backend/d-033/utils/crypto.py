import base64
import os
import hashlib
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("utf-8")


def b64url_decode(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class Ed25519Signer:
    def __init__(self, private_key: Ed25519PrivateKey, keyid: Optional[str] = None):
        self._priv = private_key
        self._pub = private_key.public_key()
        self._keyid = keyid or self._derive_keyid(self._pub)

    @staticmethod
    def _derive_keyid(pub: Ed25519PublicKey) -> str:
        raw = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(raw).hexdigest()

    @property
    def keyid(self) -> str:
        return self._keyid

    def sign(self, data: bytes) -> bytes:
        return self._priv.sign(data)

    def verify(self, data: bytes, sig: bytes) -> bool:
        try:
            self._pub.verify(sig, data)
            return True
        except Exception:
            return False

    def public_key_pem(self) -> str:
        pem = self._pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("utf-8")

    def public_key_b64(self) -> str:
        raw = self._pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return b64url_encode(raw)

    def private_key_pem(self) -> str:
        pem = self._priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pem.decode("utf-8")


def load_private_key_from_pem_file(path: str) -> Ed25519PrivateKey:
    with open(path, "rb") as f:
        data = f.read()
    return serialization.load_pem_private_key(data, password=None)


def load_private_key_from_b64(seed_b64: str) -> Ed25519PrivateKey:
    seed = b64url_decode(seed_b64) if _looks_urlsafe_b64(seed_b64) else base64.b64decode(seed_b64)
    if len(seed) != 32:
        raise ValueError("ATTESTATION_PRIVATE_KEY_B64 must decode to 32-byte Ed25519 seed")
    return Ed25519PrivateKey.from_private_bytes(seed)


def _looks_urlsafe_b64(s: str) -> bool:
    return '-' in s or '_' in s


def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def load_signer(priv_pem_file: Optional[str] = None, priv_b64: Optional[str] = None, save_generated_to: Optional[str] = None) -> Ed25519Signer:
    if priv_pem_file and os.path.exists(priv_pem_file):
        priv = load_private_key_from_pem_file(priv_pem_file)
        return Ed25519Signer(priv)
    if priv_b64:
        priv = load_private_key_from_b64(priv_b64)
        return Ed25519Signer(priv)
    priv = generate_private_key()
    if save_generated_to:
        pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        os.makedirs(os.path.dirname(save_generated_to), exist_ok=True)
        with open(save_generated_to, "wb") as f:
            f.write(pem)
    return Ed25519Signer(priv)

