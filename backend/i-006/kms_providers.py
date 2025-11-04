import base64
import os
from dataclasses import dataclass
from typing import Dict, Optional

from config import Config
from crypto_utils import aesgcm_encrypt_raw, aesgcm_decrypt_raw

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:  # pragma: no cover - optional dependency at runtime
    boto3 = None
    BotoCoreError = Exception
    ClientError = Exception


def build_aad_from_context(ctx: Dict[str, str]) -> bytes:
    # Stable ordering to ensure consistent AAD
    items = [f"{k}={ctx[k]}" for k in sorted(ctx.keys())]
    return (';'.join(items)).encode('utf-8')


class KMSClientBase:
    name = 'base'
    def encrypt(self, plaintext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        raise NotImplementedError
    def decrypt(self, ciphertext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        raise NotImplementedError
    def generate_data_key(self, key_size_bytes: int = 32, encryption_context: Optional[Dict[str, str]] = None) -> tuple[bytes, bytes]:
        raise NotImplementedError


class LocalKMSClient(KMSClientBase):
    name = 'local'

    def __init__(self, master_key: bytes):
        if len(master_key) not in (16, 24, 32):
            raise ValueError('Invalid master key length')
        self.master_key = master_key

    def encrypt(self, plaintext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        aad = build_aad_from_context(encryption_context or {})
        return aesgcm_encrypt_raw(self.master_key, plaintext, aad)

    def decrypt(self, ciphertext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        aad = build_aad_from_context(encryption_context or {})
        return aesgcm_decrypt_raw(self.master_key, ciphertext, aad)

    def generate_data_key(self, key_size_bytes: int = 32, encryption_context: Optional[Dict[str, str]] = None) -> tuple[bytes, bytes]:
        plaintext = os.urandom(key_size_bytes)
        return plaintext, self.encrypt(plaintext, encryption_context)


class AWSKMSClient(KMSClientBase):
    name = 'aws'

    def __init__(self, cmk_id: str):
        if not boto3:
            raise RuntimeError('boto3 not available')
        self.client = boto3.client('kms')
        self.cmk_id = cmk_id

    def _convert_ctx(self, ctx: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if not ctx:
            return None
        return {str(k): str(v) for k, v in ctx.items()}

    def encrypt(self, plaintext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        resp = self.client.encrypt(KeyId=self.cmk_id, Plaintext=plaintext, EncryptionContext=self._convert_ctx(encryption_context))
        return resp['CiphertextBlob']

    def decrypt(self, ciphertext: bytes, encryption_context: Optional[Dict[str, str]] = None) -> bytes:
        resp = self.client.decrypt(CiphertextBlob=ciphertext, EncryptionContext=self._convert_ctx(encryption_context))
        return resp['Plaintext']

    def generate_data_key(self, key_size_bytes: int = 32, encryption_context: Optional[Dict[str, str]] = None) -> tuple[bytes, bytes]:
        resp = self.client.generate_data_key(KeyId=self.cmk_id, KeySpec='AES_256' if key_size_bytes == 32 else None, NumberOfBytes=key_size_bytes, EncryptionContext=self._convert_ctx(encryption_context))
        return resp['Plaintext'], resp['CiphertextBlob']


_singleton_client: Optional[KMSClientBase] = None


def get_kms_client() -> KMSClientBase:
    global _singleton_client
    if _singleton_client is not None:
        return _singleton_client

    if Config.AWS_KMS_KEY_ID and boto3:
        try:
            _singleton_client = AWSKMSClient(Config.AWS_KMS_KEY_ID)
            return _singleton_client
        except Exception:
            pass

    # Local fallback
    master_key = None
    if os.path.isfile(Config.LOCAL_KMS_MASTER_KEY_PATH):
        with open(Config.LOCAL_KMS_MASTER_KEY_PATH, 'rb') as f:
            b64 = f.read()
            try:
                master_key = base64.b64decode(b64)
            except Exception:
                master_key = None
    if master_key is None:
        # Derive from env or create new
        if Config.LOCAL_KMS_MASTER_KEY_B64:
            try:
                master_key = base64.b64decode(Config.LOCAL_KMS_MASTER_KEY_B64)
            except Exception:
                pass
        if master_key is None:
            master_key = os.urandom(32)
            try:
                with open(Config.LOCAL_KMS_MASTER_KEY_PATH, 'wb') as f:
                    f.write(base64.b64encode(master_key))
            except Exception:
                pass
    _singleton_client = LocalKMSClient(master_key)
    return _singleton_client

