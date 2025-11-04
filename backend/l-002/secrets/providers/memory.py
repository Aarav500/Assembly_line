import yaml
from typing import Dict, List, Optional, Any
from .base import SecretsProvider


def _flatten(prefix: str, obj: Any, out: Dict[str, Any]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}/{k}" if prefix else str(k)
            _flatten(key, v, out)
    else:
        out[prefix] = obj


class InMemorySecretsProvider(SecretsProvider):
    def __init__(self, seed_file: Optional[str] = None):
        self._store: Dict[str, Any] = {}
        if seed_file:
            try:
                with open(seed_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                flat: Dict[str, Any] = {}
                _flatten('', data, flat)
                self._store.update(flat)
            except FileNotFoundError:
                pass

    def name(self) -> str:
        return 'memory'

    def get_secret(self, path: str) -> Optional[Any]:
        return self._store.get(path)

    def set_secret(self, path: str, value: Any) -> None:
        self._store[path] = value

    def delete_secret(self, path: str) -> bool:
        return self._store.pop(path, None) is not None

    def list_secrets(self, prefix: str = '') -> List[str]:
        if not prefix:
            return list(self._store.keys())
        return [k for k in self._store.keys() if k.startswith(prefix)]

