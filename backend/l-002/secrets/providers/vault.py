from typing import List, Optional, Any
from .base import SecretsProvider

try:
    import hvac
except Exception as e:  # pragma: no cover
    hvac = None


class VaultSecretsProvider(SecretsProvider):
    def __init__(self, addr: str, token: str, kv_mount: str = 'secret', namespace: Optional[str] = None):
        if hvac is None:
            raise RuntimeError('hvac is not available for Vault integration')
        if not addr or not token:
            raise RuntimeError('VAULT_ADDR and VAULT_TOKEN are required for Vault provider')
        self.addr = addr
        self.token = token
        self.kv_mount = kv_mount
        self.namespace = namespace
        self.client = hvac.Client(url=self.addr, token=self.token, namespace=self.namespace)
        if not self.client.is_authenticated():
            raise RuntimeError('Vault authentication failed')

    def name(self) -> str:
        return 'vault'

    def _kv2_read(self, path: str) -> Optional[Any]:
        try:
            res = self.client.secrets.kv.v2.read_secret_version(mount_point=self.kv_mount, path=path)
            return res['data']['data']
        except hvac.exceptions.InvalidPath:
            return None

    def _kv2_write(self, path: str, data: Any) -> None:
        # If value is scalar, wrap in {'value': value}
        payload = data if isinstance(data, dict) else { 'value': data }
        self.client.secrets.kv.v2.create_or_update_secret(mount_point=self.kv_mount, path=path, secret=payload)

    def _kv2_delete(self, path: str) -> bool:
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(mount_point=self.kv_mount, path=path)
            return True
        except hvac.exceptions.InvalidPath:
            return False

    def get_secret(self, path: str) -> Optional[Any]:
        return self._kv2_read(path)

    def set_secret(self, path: str, value: Any) -> None:
        self._kv2_write(path, value)

    def delete_secret(self, path: str) -> bool:
        return self._kv2_delete(path)

    def list_secrets(self, prefix: str = '') -> List[str]:
        # kv v2 list returns keys relative to path; we recursively list
        results: List[str] = []
        base = prefix.rstrip('/')
        to_visit = [base] if base else ['']
        seen = set()
        while to_visit:
            current = to_visit.pop()
            if current in seen:
                continue
            seen.add(current)
            rel_path = current if current else ''
            try:
                res = self.client.secrets.kv.v2.list_secrets(mount_point=self.kv_mount, path=rel_path)
                keys = res['data']['keys']
                for k in keys:
                    if k.endswith('/'):
                        to_visit.append(f"{rel_path}{k}")
                    else:
                        full = f"{rel_path}{k}" if rel_path else k
                        results.append(full)
            except hvac.exceptions.InvalidPath:
                # If listing fails but reading works, it's a leaf
                if rel_path:
                    val = self._kv2_read(rel_path)
                    if val is not None:
                        results.append(rel_path)
        # Apply prefix filter for safety
        if base:
            results = [r for r in results if r.startswith(base)]
        return results

