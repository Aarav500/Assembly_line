import json
import os
from typing import Any, Dict, List, Optional


class AppConfig:
    def __init__(self):
        self.vault_addr = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self.vault_token = os.environ.get("VAULT_TOKEN")
        self.vault_namespace = os.environ.get("VAULT_NAMESPACE")
        self.vault_auth_method = os.environ.get("VAULT_AUTH_METHOD", "token")
        self.vault_k8s_role = os.environ.get("VAULT_K8S_ROLE")
        self.kubernetes_jwt_path = os.environ.get("KUBERNETES_JWT_PATH", "/var/run/secrets/kubernetes.io/serviceaccount/token")

        self.vault_mount_kv = os.environ.get("VAULT_MOUNT_KV", "secret")
        self.vault_mount_database = os.environ.get("VAULT_MOUNT_DB", "database")

        # Rotation config: JSON array path or inline JSON string
        self.rotation_jobs: Optional[List[Dict[str, Any]]] = self._load_rotation_jobs()

    def _load_rotation_jobs(self) -> Optional[List[Dict[str, Any]]]:
        config_path = os.environ.get("ROTATION_CONFIG_PATH")
        inline = os.environ.get("ROTATION_JOBS_JSON")
        if inline:
            try:
                data = json.loads(inline)
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                return None
        # default sample config if exists
        default_path = os.path.join(os.path.dirname(__file__), "config", "rotation.sample.json")
        if os.path.exists(default_path):
            try:
                with open(default_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                return None
        return None

