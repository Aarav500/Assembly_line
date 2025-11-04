from __future__ import annotations
import json
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple
from hashlib import sha256
from cryptography.fernet import Fernet, InvalidToken


class TTLCache:
    def __init__(self, ttl_seconds: int = 60, maxsize: int = 1024):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            val, expiry = item
            if time.time() > expiry:
                del self._store[key]
                return None
            return val

    def set(self, key: str, value: Any):
        with self._lock:
            if len(self._store) >= self.maxsize:
                # Simple eviction: remove one arbitrary old item
                oldest_key = next(iter(self._store))
                self._store.pop(oldest_key, None)
            self._store[key] = (value, time.time() + self.ttl)

    def clear(self):
        with self._lock:
            self._store.clear()


class SecretStore:
    def __init__(self, db_path: str, key: bytes, cache_ttl: int = 60, on_secret_added=None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._fernet = Fernet(key)
        self._lock = threading.RLock()
        self._cache = TTLCache(ttl_seconds=cache_ttl)
        self._on_secret_added = on_secret_added
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.db_path):
            self._persist()
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    self._data = raw
        except Exception:
            # If corrupted, start fresh (could log warning)
            self._data = {}

    def _persist(self):
        tmp = f"{self.db_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        os.replace(tmp, self.db_path)

    def _now(self) -> int:
        return int(time.time())

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        exp = entry.get("expires_at")
        return isinstance(exp, int) and exp > 0 and exp <= self._now()

    def list(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            result: Dict[str, Dict[str, Any]] = {}
            for k, v in self._data.items():
                if self._is_expired(v):
                    continue
                result[k] = {
                    "name": k,
                    "created_at": v.get("created_at"),
                    "expires_at": v.get("expires_at"),
                    "fingerprint": v.get("fingerprint"),
                    "metadata": v.get("metadata", {}),
                }
            return result

    def set(self, name: str, plaintext: str, ttl_seconds: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        if not isinstance(plaintext, str) or plaintext == "":
            raise ValueError("Secret value must be a non-empty string")
        with self._lock:
            created_at = self._now()
            expires_at = created_at + ttl_seconds if ttl_seconds and ttl_seconds > 0 else None
            ciphertext = self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
            fingerprint = sha256(plaintext.encode("utf-8")).hexdigest()
            self._data[name] = {
                "ciphertext": ciphertext,
                "created_at": created_at,
                "expires_at": expires_at,
                "metadata": metadata or {},
                "fingerprint": fingerprint,
            }
            self._persist()
            self._cache.set(name, plaintext)
            if self._on_secret_added:
                try:
                    self._on_secret_added(plaintext)
                except Exception:
                    pass

    def get(self, name: str, reveal: bool = False) -> Dict[str, Any]:
        with self._lock:
            entry = self._data.get(name)
            if not entry or self._is_expired(entry):
                raise KeyError("Secret not found or expired")
            base = {
                "name": name,
                "created_at": entry.get("created_at"),
                "expires_at": entry.get("expires_at"),
                "metadata": entry.get("metadata", {}),
                "fingerprint": entry.get("fingerprint"),
            }
            if not reveal:
                base["value"] = self._mask_preview(self._peek_plaintext(name))
                return base
            val = self._peek_plaintext(name)
            base["value"] = val
            return base

    def delete(self, name: str) -> bool:
        with self._lock:
            existed = name in self._data
            if existed:
                self._data.pop(name, None)
                self._persist()
                self._cache.clear()
            return existed

    def _peek_plaintext(self, name: str) -> str:
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        with self._lock:
            entry = self._data.get(name)
            if not entry:
                raise KeyError("Secret not found")
            ciphertext = entry.get("ciphertext")
            try:
                plaintext = self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
            except (InvalidToken, Exception) as e:
                raise ValueError("Failed to decrypt secret") from e
            self._cache.set(name, plaintext)
            return plaintext

    @staticmethod
    def _mask_preview(value: str) -> str:
        if value is None:
            return "***"
        if len(value) <= 4:
            return "***"
        return f"***{value[-4:]}"

