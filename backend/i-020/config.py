import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from security.policy import Policy, policy_from_dict


def _json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class AppConfig:
    # Endpoints
    STANDARD_BACKEND_URL: str
    CONFIDENTIAL_BACKEND_URL: str

    # Attestation configuration
    ATTESTATION_JWKS_URL: Optional[str]
    ATTESTATION_PUBKEY_PEM: Optional[str]

    # Routing
    SENSITIVE_MODELS: Dict[str, Policy] = field(default_factory=dict)
    FAIL_MODE: str = "fail-closed"  # or "fail-open"

    # Enforcement flags
    ENFORCE_ATTESTATION: bool = True
    ENFORCE_TLS: bool = False  # if mTLS to backends is required; not implemented in this sample

    # Logging
    LOG_LEVEL: str = "INFO"

    # Timeouts
    BACKEND_TIMEOUT_SECONDS: float = 30.0

    # Cache / Health check
    ATTESTATION_CACHE_SECONDS: int = 300


DEFAULT_SENSITIVE_MODELS = {
    # Example model policies
    "vault-gpt": {
        "required_tee": ["tdx", "sev-snp", "nitro"],
        "min_svn": 0,
        "allowed_mrenclave": [],
        "allowed_mrsigner": [],
        "allow_debug": False,
        "require_hw_protected": True,
        "vendor": [],
    },
    "gpt-4o-pro-sensitive": {
        "required_tee": ["tdx"],
        "min_svn": 0,
        "allowed_mrenclave": [],
        "allowed_mrsigner": [],
        "allow_debug": False,
        "require_hw_protected": True,
        "vendor": ["intel"],
    },
}


def load_config() -> AppConfig:
    # Load sensitive models policies
    sensitive_models_env = _json_env("SENSITIVE_MODELS_JSON", DEFAULT_SENSITIVE_MODELS)

    policies: Dict[str, Policy] = {}
    for model_name, policy_dict in sensitive_models_env.items():
        policies[model_name] = policy_from_dict(policy_dict)

    pubkey_pem = os.getenv("ATTESTATION_PUBKEY_PEM")
    if pubkey_pem and not pubkey_pem.strip().startswith("-----BEGIN"):
        # Support escaped newlines via env var
        pubkey_pem = pubkey_pem.replace("\\n", "\n")

    return AppConfig(
        STANDARD_BACKEND_URL=os.getenv("STANDARD_BACKEND_URL", "http://localhost:9000"),
        CONFIDENTIAL_BACKEND_URL=os.getenv("CONFIDENTIAL_BACKEND_URL", "http://localhost:9100"),
        ATTESTATION_JWKS_URL=os.getenv("ATTESTATION_JWKS_URL"),
        ATTESTATION_PUBKEY_PEM=pubkey_pem,
        SENSITIVE_MODELS=policies,
        FAIL_MODE=os.getenv("FAIL_MODE", "fail-closed"),
        ENFORCE_ATTESTATION=_bool_env("ENFORCE_ATTESTATION", True),
        ENFORCE_TLS=_bool_env("ENFORCE_TLS", False),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        BACKEND_TIMEOUT_SECONDS=float(os.getenv("BACKEND_TIMEOUT_SECONDS", "30")),
        ATTESTATION_CACHE_SECONDS=int(os.getenv("ATTESTATION_CACHE_SECONDS", "300")),
    )

