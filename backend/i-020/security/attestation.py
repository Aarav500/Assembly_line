import time
import json
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import requests
import jwt
from jwt import PyJWKClient

from utils.logging import get_logger
from security.policy import Policy


logger = get_logger(__name__)


class AttestationError(Exception):
    pass


class AttestationVerifier:
    def __init__(self, jwks_url: Optional[str] = None, pubkey_pem: Optional[str] = None, cache_ttl: int = 300):
        if not jwks_url and not pubkey_pem:
            logger.warning("attestation_verifier_no_keys", extra={"note": "Attestation verification disabled: no JWKS or public key provided"})
        self.jwks_url = jwks_url
        self.pubkey_pem = pubkey_pem
        self.cache_ttl = cache_ttl
        self._jwks_client = PyJWKClient(self.jwks_url) if self.jwks_url else None
        self._cached_keys = None
        self._cached_keys_at = 0

    def _get_signing_key(self, token: str):
        if self._jwks_client:
            return self._jwks_client.get_signing_key_from_jwt(token).key
        if self.pubkey_pem:
            return self.pubkey_pem
        raise AttestationError("No verification keys configured")

    def verify(self, token: str, policy: Optional[Policy]) -> Dict[str, Any]:
        if not token:
            raise AttestationError("Missing attestation token")

        try:
            key = self._get_signing_key(token)
            claims = jwt.decode(token, key=key, algorithms=["RS256", "ES256"], options={"require": ["exp", "iat", "tee"]})
        except Exception as e:
            logger.exception("attestation_jwt_decode_error")
            raise AttestationError(f"Invalid attestation token: {e}")

        now = int(time.time())
        if claims.get("exp", 0) < now:
            raise AttestationError("Attestation token expired")

        # Minimal structural checks
        tee = (claims.get("tee") or {}).copy()
        tee_type = str(tee.get("type", "")).lower()
        vendor = str(tee.get("vendor", "")).lower()
        svn = int(tee.get("svn", 0))
        mrenclave = str(tee.get("mrenclave", "")).lower()
        mrsigner = str(tee.get("mrsigner", "")).lower()
        debug = bool(tee.get("debug", False))
        hw = bool(tee.get("hw", True))  # indicates hw-backed

        if policy:
            if policy.require_hw_protected and not hw:
                raise AttestationError("Hardware-backed protection required")
            if policy.required_tee and tee_type not in policy.required_tee:
                raise AttestationError(f"TEE '{tee_type}' not in required set")
            if policy.vendor and vendor not in policy.vendor:
                raise AttestationError(f"Vendor '{vendor}' not allowed")
            if svn < policy.min_svn:
                raise AttestationError(f"Security version {svn} below minimum {policy.min_svn}")
            if policy.allowed_mrenclave and mrenclave not in policy.allowed_mrenclave:
                raise AttestationError("MRENCLAVE not allowed")
            if policy.allowed_mrsigner and mrsigner not in policy.allowed_mrsigner:
                raise AttestationError("MRSIGNER not allowed")
            if not policy.allow_debug and debug:
                raise AttestationError("Debug enclaves not allowed")

        logger.info("attestation_verified", extra={"tee": tee_type, "vendor": vendor, "svn": svn})
        return claims

