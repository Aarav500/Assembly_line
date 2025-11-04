from typing import Dict, Any, Optional
import requests

from security.policy import Policy
from security.attestation import AttestationVerifier, AttestationError


class ConfidentialClient:
    def __init__(self, base_url: str, timeout: float = 30.0, verifier: Optional[AttestationVerifier] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verifier = verifier

    def infer(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, policy: Optional[Policy] = None) -> Dict[str, Any]:
        headers = dict(headers or {})
        headers["X-Confidential-Compute"] = "required"

        if self.verifier is not None:
            token = self._fetch_attestation_token()
            self.verifier.verify(token, policy)
            headers["X-Verified-Attestation"] = "true"

        url = f"{self.base_url}/v1/infer"
        resp = requests.post(url, json=payload, timeout=self.timeout, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def _fetch_attestation_token(self) -> str:
        url = f"{self.base_url}/.well-known/attestation"
        resp = requests.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise AttestationError(f"Failed to fetch attestation token: {resp.status_code}")
        data = resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else None
        token = (data or {}).get("token") if data else resp.text.strip()
        if not token:
            raise AttestationError("Empty attestation token")
        return token

