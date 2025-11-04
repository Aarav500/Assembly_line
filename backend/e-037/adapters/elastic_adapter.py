import base64
import json
from typing import Optional
import requests

class ElasticAdapter:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None, api_key: Optional[str] = None, verify_ssl: bool = True, timeout: int = 15):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username is not None and self.password is not None:
            # requests handles basic auth separately, but we can use HTTPBasicAuth too; here we set later
            pass
        return headers

    def _auth(self):
        if self.api_key:
            return None
        if self.username is not None and self.password is not None:
            return (self.username, self.password)
        return None

    def ensure_ilm_policy(self, name: str, hot_days: Optional[int], warm_days: Optional[int], delete_after_days: int):
        phases = {
            "hot": {
                "min_age": "0ms",
                "actions": {}
            },
            "delete": {
                "min_age": f"{int(delete_after_days)}d",
                "actions": {"delete": {}}
            }
        }
        if hot_days is not None and int(hot_days) > 0:
            phases["hot"]["actions"]["set_priority"] = {"priority": 100}
            phases["hot"]["actions"]["rollover"] = {"max_age": f"{int(hot_days)}d"}
        if warm_days is not None and int(warm_days) > 0:
            phases["warm"] = {
                "min_age": f"{int(warm_days)}d",
                "actions": {"set_priority": {"priority": 50}}
            }
        body = {"policy": {"phases": phases}}
        url = f"{self.base_url}/_ilm/policy/{name}"
        resp = requests.put(url, headers=self._headers(), auth=self._auth(), data=json.dumps(body), timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to put ILM policy {name}: {resp.status_code} {resp.text}")
        return True

    def ensure_index_template(self, index_pattern: str, ilm_policy_name: str, template_name: Optional[str] = None):
        tname = template_name or f"tpl-{ilm_policy_name}"
        body = {
            "index_patterns": [index_pattern],
            "template": {
                "settings": {
                    "index.lifecycle.name": ilm_policy_name,
                    # If using rollover, you should also set an alias here and manage rollover separately.
                }
            },
            "priority": 500
        }
        url = f"{self.base_url}/_index_template/{tname}"
        resp = requests.put(url, headers=self._headers(), auth=self._auth(), data=json.dumps(body), timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to put index template {tname}: {resp.status_code} {resp.text}")
        return True

    def list_ilm_policies(self):
        url = f"{self.base_url}/_ilm/policy"
        resp = requests.get(url, headers=self._headers(), auth=self._auth(), timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list ILM policies: {resp.status_code} {resp.text}")
        return resp.json()

    def delete_ilm_policy(self, name: str):
        url = f"{self.base_url}/_ilm/policy/{name}"
        resp = requests.delete(url, headers=self._headers(), auth=self._auth(), timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code not in (200, 404):
            raise RuntimeError(f"Failed to delete ILM policy {name}: {resp.status_code} {resp.text}")
        return resp.status_code == 200

