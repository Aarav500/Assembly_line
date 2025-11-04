import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def aesgcm_encrypt_raw(key: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext, aad)
    # Return nonce | ciphertext+tag
    return nonce + ct


def aesgcm_decrypt_raw(key: bytes, combined: bytes, aad: bytes | None = None) -> bytes:
    if len(combined) < 12 + 16:
        raise ValueError('ciphertext too short')
    nonce = combined[:12]
    ct = combined[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, aad)


def aesgcm_encrypt(byok: bytes, plaintext: bytes, aad: bytes | None = None) -> bytes:
    return aesgcm_encrypt_raw(byok, plaintext, aad)


def aesgcm_decrypt(byok: bytes, combined: bytes, aad: bytes | None = None) -> bytes:
    return aesgcm_decrypt_raw(byok, combined, aad)

