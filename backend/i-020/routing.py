import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests

from config import AppConfig
from utils.logging import get_logger
from security.policy import Policy
from security.attestation import AttestationVerifier, AttestationError
from clients.standard_client import StandardClient
from clients.confidential_client import ConfidentialClient


logger = get_logger(__name__)


class BackendError(Exception):
    pass


class AttestationRouteError(Exception):
    pass


@dataclass
class RouteDecision:
    target: str  # one of: "confidential", "standard", "deny"
    reason: Optional[str] = None
    policy: Optional[Policy] = None


class SecureRouter:
    class AttestationError(AttestationError):
        pass

    class BackendError(BackendError):
        pass

    def __init__(self, config: AppConfig):
        self.config = config
        self.verifier = AttestationVerifier(
            jwks_url=config.ATTESTATION_JWKS_URL,
            pubkey_pem=config.ATTESTATION_PUBKEY_PEM,
            cache_ttl=config.ATTESTATION_CACHE_SECONDS,
        )
        self.standard = StandardClient(base_url=config.STANDARD_BACKEND_URL, timeout=config.BACKEND_TIMEOUT_SECONDS)
        self.confidential = ConfidentialClient(
            base_url=config.CONFIDENTIAL_BACKEND_URL,
            timeout=config.BACKEND_TIMEOUT_SECONDS,
            verifier=self.verifier if config.ENFORCE_ATTESTATION else None,
        )

    def readiness(self) -> Dict[str, Any]:
        ok = True
        details = {}
        # Check basic connectivity to backends (non-blocking, short timeouts)
        for name, url in ("standard", self.config.STANDARD_BACKEND_URL), ("confidential", self.config.CONFIDENTIAL_BACKEND_URL):
            try:
                resp = requests.get(f"{url}/healthz", timeout=2)
                details[name] = resp.status_code == 200
            except Exception:
                details[name] = False
                ok = False
        return {"ok": ok, "details": details}

    def decide(self, model_name: str, context: Dict[str, Any]) -> RouteDecision:
        # Determine whether the model is sensitive
        policy = self.lookup_policy(model_name)
        if policy:
            logger.info("route_decision", extra={"model": model_name, "target": "confidential"})
            return RouteDecision(target="confidential", reason="sensitive_model", policy=policy)

        # Non-sensitive -> standard backend
        logger.info("route_decision", extra={"model": model_name, "target": "standard"})
        return RouteDecision(target="standard")

    def lookup_policy(self, model_name: str) -> Optional[Policy]:
        # Exact match or prefix match (e.g., family variants)
        if model_name in self.config.SENSITIVE_MODELS:
            return self.config.SENSITIVE_MODELS[model_name]
        for name, policy in self.config.SENSITIVE_MODELS.items():
            if model_name.startswith(name + ":") or model_name.startswith(name + "/"):
                return policy
        return None

    def execute(self, decision: RouteDecision, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "X-Route-Decision": decision.target,
            "X-Request-Timestamp": str(int(time.time())),
        }

        if decision.target == "standard":
            try:
                return self.standard.infer(payload, headers=headers)
            except Exception as e:
                logger.exception("standard_backend_error")
                raise self.BackendError(str(e))

        if decision.target == "confidential":
            if not self.config.CONFIDENTIAL_BACKEND_URL:
                if self.config.FAIL_MODE == "fail-open":
                    logger.warning("conf_backend_missing_fail_open")
                    return self.standard.infer(payload, headers=headers)
                raise self.BackendError("Confidential backend URL not configured")

            try:
                return self.confidential.infer(payload, headers=headers, policy=decision.policy)
            except AttestationError as e:
                if self.config.FAIL_MODE == "fail-open":
                    logger.warning("attestation_failed_fail_open", extra={"error": str(e)})
                    return self.standard.infer(payload, headers=headers)
                raise self.AttestationError(str(e))
            except Exception as e:
                logger.exception("confidential_backend_error")
                raise self.BackendError(str(e))

        if decision.target == "deny":
            return {"denied": True, "reason": decision.reason or "policy_denied"}

        raise self.BackendError(f"Unknown route target: {decision.target}")

