import base64
import json
import os
from functools import lru_cache
from typing import Optional


class SecretResolver:
    """Resolves placeholders for env, Vault, and AWS Secrets Manager."""

    def __init__(self) -> None:
        self._vault_client = None
        self._aws_clients = {}

    # ENV
    @staticmethod
    def resolve_env(var_name: str, default: Optional[str] = None) -> str:
        val = os.getenv(var_name, default)
        if val is None:
            raise KeyError(f"Environment variable '{var_name}' not set and no default provided")
        return str(val)

    # Vault
    def _get_vault_client(self):
        if self._vault_client is not None:
            return self._vault_client
        try:
            import hvac  # type: ignore
        except Exception as e:
            raise RuntimeError("hvac is required for Vault resolution. Add 'hvac' to dependencies.") from e

        addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        token = os.getenv("VAULT_TOKEN")
        if not token:
            raise RuntimeError("VAULT_TOKEN is not set for Vault secret resolution")
        verify_env = os.getenv("VAULT_VERIFY", "true").strip().lower()
        verify = verify_env not in ("0", "false", "no")

        client = hvac.Client(url=addr, token=token, verify=verify)
        if not client.is_authenticated():
            raise RuntimeError("Failed to authenticate to Vault with provided token")
        self._vault_client = client
        return client

    @lru_cache(maxsize=256)
    def resolve_vault(self, path: str, key: Optional[str] = None, default: Optional[str] = None) -> str:
        client = self._get_vault_client()
        resp = client.read(path)
        if not resp:
            if default is not None:
                return default
            raise KeyError(f"Vault secret not found at path '{path}'")
        data = resp.get("data") or {}
        # Handle KV v2 nested structure
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            data = data["data"]
        if key:
            if key not in data:
                if default is not None:
                    return default
                raise KeyError(f"Key '{key}' not found in Vault secret at '{path}'")
            return str(data[key])
        # No key specified: return JSON string of the data
        try:
            return json.dumps(data)
        except Exception:
            return str(data)

    # AWS Secrets Manager
    def _get_aws_sm_client(self, region_name: Optional[str] = None):
        region = region_name or os.getenv("AWS_REGION", "us-east-1")
        if region in self._aws_clients:
            return self._aws_clients[region]
        try:
            import boto3  # type: ignore
        except Exception as e:
            raise RuntimeError("boto3 is required for AWS Secrets Manager resolution. Add 'boto3' to dependencies.") from e
        client = boto3.client("secretsmanager", region_name=region)
        self._aws_clients[region] = client
        return client

    @lru_cache(maxsize=256)
    def resolve_aws(self, secret_id: str, json_key: Optional[str] = None, default: Optional[str] = None) -> str:
        client = self._get_aws_sm_client()
        try:
            resp = client.get_secret_value(SecretId=secret_id)
        except Exception as e:
            if default is not None:
                return default
            raise RuntimeError(f"Failed to get AWS secret '{secret_id}': {e}") from e
        if "SecretString" in resp and resp["SecretString"] is not None:
            secret_value = resp["SecretString"]
        else:
            # Binary secret
            b64 = resp.get("SecretBinary")
            if not b64:
                if default is not None:
                    return default
                raise RuntimeError(f"AWS secret '{secret_id}' returned no data")
            secret_value = base64.b64decode(b64).decode("utf-8")
        if json_key:
            try:
                obj = json.loads(secret_value)
                if json_key not in obj:
                    if default is not None:
                        return default
                    raise KeyError(f"Key '{json_key}' not found in AWS secret '{secret_id}'")
                return str(obj[json_key])
            except json.JSONDecodeError:
                if default is not None:
                    return default
                raise RuntimeError(f"AWS secret '{secret_id}' is not JSON but a json_key '{json_key}' was specified")
        return str(secret_value)

