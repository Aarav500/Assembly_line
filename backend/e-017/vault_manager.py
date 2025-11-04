import json
import os
import time
from typing import Dict, Optional, Tuple

import hvac

from utils import generate_secret


class VaultManager:
    def __init__(
        self,
        address: str,
        token: Optional[str] = None,
        namespace: Optional[str] = None,
        auth_method: str = "token",
        k8s_role: Optional[str] = None,
        k8s_jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token",
        timeout: int = 10,
        verify: Optional[bool] = None,
    ):
        self.address = address
        self._token = token
        self.namespace = namespace
        self.auth_method = (auth_method or "token").lower()
        self.k8s_role = k8s_role
        self.k8s_jwt_path = k8s_jwt_path
        self.verify = verify if verify is not None else self._get_verify()
        self.timeout = timeout

        self.client = hvac.Client(url=self.address, token=self._token, namespace=self.namespace, verify=self.verify, timeout=self.timeout)

    def _get_verify(self) -> bool:
        env = os.environ.get("VAULT_SKIP_VERIFY")
        if env is None:
            return True
        return not (env.lower() in ("1", "true", "yes"))

    def is_authenticated(self) -> bool:
        try:
            return bool(self.client.is_authenticated())
        except Exception:
            return False

    def authenticate(self):
        if self.auth_method == "token":
            if not self._token:
                raise RuntimeError("VAULT_TOKEN is required for token auth.")
            self.client.token = self._token
            if not self.client.is_authenticated():
                raise RuntimeError("Vault token authentication failed.")
            return
        elif self.auth_method in ("kubernetes", "k8s"):
            if not self.k8s_role:
                raise RuntimeError("VAULT_K8S_ROLE is required for Kubernetes auth.")
            jwt = self._read_file(self.k8s_jwt_path)
            response = self.client.auth.kubernetes.login(role=self.k8s_role, jwt=jwt)
            if not self.client.is_authenticated():
                raise RuntimeError("Vault Kubernetes authentication failed.")
            return response
        else:
            raise ValueError(f"Unsupported auth method: {self.auth_method}")

    def _read_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # KV v2 read
    def read_kv_secret(self, path: str, mount_point: str = "secret", version: Optional[int] = None) -> Tuple[Dict, Dict]:
        resp = self.client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount_point, version=version)
        data = resp.get("data", {}).get("data", {})
        metadata = resp.get("data", {}).get("metadata", {})
        return data, metadata

    # KV v2 write
    def write_kv_secret(self, path: str, data: Dict, mount_point: str = "secret") -> Dict:
        resp = self.client.secrets.kv.v2.create_or_update_secret(path=path, secret=data, mount_point=mount_point)
        return resp.get("data", {})

    def rotate_kv_random_secret(
        self,
        path: str,
        field: str = "password",
        length: int = 32,
        mount_point: str = "secret",
        alphabet: Optional[str] = None,
        preserve_fields: Optional[Dict] = None,
    ) -> Tuple[str, Dict]:
        preserve_fields = preserve_fields or {}
        # read current to preserve other fields
        try:
            current_data, _ = self.read_kv_secret(path=path, mount_point=mount_point)
        except Exception:
            current_data = {}
        new_value = generate_secret(length=length, alphabet=alphabet)
        new_data = {**current_data, **preserve_fields, field: new_value}
        metadata = self.write_kv_secret(path=path, data=new_data, mount_point=mount_point)
        return new_value, metadata

    # Dynamic database creds
    def generate_database_credentials(self, role: str, mount_point: str = "database") -> Dict:
        # hvac returns a dict with lease info
        resp = self.client.secrets.database.generate_credentials(name=role, mount_point=mount_point)
        return resp

    # Lease operations
    def renew_lease(self, lease_id: str, increment: Optional[int] = None) -> Dict:
        if increment:
            return self.client.sys.renew_lease(lease_id=lease_id, increment=increment)
        return self.client.sys.renew_lease(lease_id=lease_id)

    def lookup_lease(self, lease_id: str) -> Dict:
        return self.client.sys.lookup_lease(lease_id=lease_id)

    def revoke_lease(self, lease_id: str) -> None:
        self.client.sys.revoke_lease(lease_id=lease_id)

    # Database root rotation
    def rotate_database_root(self, mount_point: str, connection_name: str) -> None:
        # Rotates the root credentials for the given connection
        self.client.secrets.database.rotate_root(name=connection_name, mount_point=mount_point)

