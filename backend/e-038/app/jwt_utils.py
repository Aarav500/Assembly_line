from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4
import jwt
from jwt import PyJWKClient, PyJWKSet
from flask import current_app


def _get_nested_claim(payload: Dict[str, Any], path: Optional[str]) -> Any:
    if not path:
        return None
    parts = path.split(".")
    cur = payload
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


def verify_id_token(token: str, provider) -> Dict[str, Any]:
    alg = provider.algorithm or "RS256"
    if provider.jwks_uri:
        jwk_client = PyJWKClient(provider.jwks_uri)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        key = signing_key.key
    elif provider.jwks_json:
        jwk_set = PyJWKSet.from_json(provider.jwks_json)
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = None
        for k in jwk_set.keys:
            if k.key_id == kid:
                key = k.key
                break
        if key is None:
            raise jwt.InvalidKeyError("No matching key id in JWKS")
    else:
        raise jwt.InvalidKeyError("Provider has no JWKS configured")

    options = {"require": ["exp", "iat"], "verify_aud": True, "verify_iss": True}
    payload = jwt.decode(
        token,
        key=key,
        algorithms=[alg],
        audience=provider.audience,
        issuer=provider.issuer,
        options=options,
        leeway=30,
    )
    return payload


def issue_session_token(sub: str, role_name: str, environment_name: str) -> Dict[str, Any]:
    ttl = int(current_app.config.get("SESSION_TTL_SECONDS", 3600))
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl)
    jti = str(uuid4())
    claims = {
        "iss": current_app.config.get("SERVICE_ISSUER", "urn:identity-federation-service"),
        "sub": sub,
        "role": role_name,
        "env": environment_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti,
    }
    token = jwt.encode(claims, current_app.config["SESSION_SIGNING_SECRET"], algorithm=current_app.config["SESSION_SIGNING_ALG"])
    return {"token": token, "claims": claims}


def introspect_session_token(token: str) -> Dict[str, Any]:
    claims = jwt.decode(
        token,
        key=current_app.config["SESSION_SIGNING_SECRET"],
        algorithms=[current_app.config["SESSION_SIGNING_ALG"]],
        options={"require": ["exp", "iat", "jti"], "verify_aud": False},
        issuer=current_app.config.get("SERVICE_ISSUER", "urn:identity-federation-service"),
    )
    return claims


def claims_match_requirement(payload: Dict[str, Any], required_claim: Optional[str], required_value: Optional[str]) -> bool:
    if not required_claim:
        return True
    val = _get_nested_claim(payload, required_claim)
    if val is None:
        return False
    if isinstance(val, list):
        return required_value in [str(x) for x in val]
    return str(val) == str(required_value)

