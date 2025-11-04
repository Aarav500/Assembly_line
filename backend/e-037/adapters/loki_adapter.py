import os
import requests
import yaml
from typing import List, Optional

class LokiAdapter:
    def __init__(self, runtime_config_path: str, admin_url: Optional[str] = None, timeout: int = 10):
        self.runtime_config_path = runtime_config_path
        self.admin_url = admin_url.rstrip("/") if admin_url else None
        self.timeout = timeout

    def generate_runtime_config(self, tenants: List[dict], default_retention_days: Optional[int] = None) -> str:
        overrides = {}
        if default_retention_days is not None:
            overrides["default"] = {"retention_period": f"{int(default_retention_days) * 24}h"}
        for t in tenants or []:
            tid = t.get("id")
            r = t.get("retention_days")
            if not tid or r is None:
                continue
            overrides[tid] = {"retention_period": f"{int(r) * 24}h"}
        data = {"overrides": overrides}
        return yaml.safe_dump(data, sort_keys=True)

    def write_runtime_config(self, content: str):
        os.makedirs(os.path.dirname(self.runtime_config_path), exist_ok=True)
        with open(self.runtime_config_path, "w", encoding="utf-8") as f:
            f.write(content)

    def reload_runtime_config(self):
        if not self.admin_url:
            return False, "LOKI_ADMIN_URL not set"
        try:
            # Loki admin reload endpoint
            # Requires -config.expand-env && -server.http-listen-port admin and auth enabled appropriately
            url = f"{self.admin_url}/loki/api/v1/admin/reload"
            resp = requests.post(url, timeout=self.timeout)
            if resp.status_code in (200, 204):
                return True, "reloaded"
            return False, f"status={resp.status_code} body={resp.text}"
        except Exception as e:
            return False, str(e)

    def generate_base_config(self, enable_retention: bool = True) -> str:
        # A minimal Loki single process config with boltdb-shipper and compactor retention
        base = {
            "auth_enabled": False,
            "server": {"http_listen_port": 3100},
            "common": {
                "path_prefix": "/tmp/loki",
                "storage": {"filesystem": {"chunks_directory": "/tmp/loki/chunks", "rules_directory": "/tmp/loki/rules"}},
                "replication_factor": 1,
                "ring": {"instance_addr": "127.0.0.1", "kvstore": {"store": "inmemory"}},
            },
            "schema_config": {
                "configs": [
                    {
                        "from": "2020-10-24",
                        "store": "boltdb-shipper",
                        "object_store": "filesystem",
                        "schema": "v13",
                        "index": {"prefix": "loki_index_", "period": "24h"},
                    }
                ]
            },
            "storage_config": {
                "boltdb_shipper": {"active_index_directory": "/tmp/loki/index", "cache_location": "/tmp/loki/cache", "shared_store": "filesystem"},
                "filesystem": {"directory": "/tmp/loki/chunks"},
            },
            "compactor": {"working_directory": "/tmp/loki/compactor", "compaction_interval": "5m", "retention_enabled": bool(enable_retention)},
            "limits_config": {
                # fallbacks; runtime-config overrides will take precedence if configured in Loki
            },
            "runtime_config": {"file": "{runtime_config_path}"},
            "ruler": {"storage": {"type": "local", "local": {"directory": "/tmp/loki/rules"}}, "rule_path": "/tmp/loki/rules"},
        }
        # Insert the runtime config path placeholder by keeping braces
        yml = yaml.safe_dump(base, sort_keys=False)
        return yml.replace("{runtime_config_path}", os.environ.get("LOKI_RUNTIME_CONFIG_PATH", "generated/loki-runtime-config.yaml"))

