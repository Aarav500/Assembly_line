import re
import secrets
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, Response, request, g, jsonify, current_app


DEFAULT_POLICY = {
    "enabled": True,
    "exclude_paths": [r"^/__security/.*$"],
    "csp": {
        "enabled": True,
        "report_only": False,
        "add_nonce": True,
        "nonce_paths": [r".*"],  # apply nonce to all by default
        "directives": {
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "style-src": ["'self'"],
            "img-src": ["'self'", "data:"],
            "font-src": ["'self'", "data:"],
            "connect-src": ["'self'"],
            "object-src": ["'none'"],
            "base-uri": ["'self'"],
            "frame-ancestors": ["'none'"],
            "upgrade-insecure-requests": [],
        },
        "report_to": None,
        "report_uri": None,
    },
    "cors": {
        "enabled": True,
        "allowed_origins": ["https://example.com"],  # change to your origin(s)
        "allow_credentials": False,
        "allowed_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allowed_headers": ["Content-Type", "Authorization"],
        "exposed_headers": [],
        "max_age": 600,
        "path_overrides": [],  # [{"pattern": "^/public/.*$", "policy": {"allowed_origins": ["*"]}}]
    },
    "headers": {
        "hsts": {"enabled": True, "max_age": 31536000, "include_subdomains": True, "preload": False},
        "x_frame_options": "DENY",  # or SAMEORIGIN
        "x_content_type_options": "nosniff",
        "referrer_policy": "strict-origin-when-cross-origin",
        "permissions_policy": "geolocation=(), microphone=(), camera=()",
        "cross_origin_opener_policy": "same-origin",
        "cross_origin_embedder_policy": "require-corp",
        "cross_origin_resource_policy": "same-origin",
    },
}


class SecurityManager:
    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self._policy: Dict[str, Any] = deep_merge(deepcopy(DEFAULT_POLICY), policy or {})
        self._app: Optional[Flask] = None

    # Public API
    def init_app(self, app: Flask):
        self._app = app

        # Register template helper for CSP nonce
        @app.context_processor
        def inject_csp_nonce():
            return {"csp_nonce": self.get_csp_nonce}

        # Security endpoints
        @app.get("/__security/suggestions")
        def security_suggestions():
            return jsonify(self.get_suggestions())

        @app.get("/__security/policy")
        def security_policy_get():
            return jsonify(self.get_policy(redacted=True))

        @app.patch("/__security/policy")
        def security_policy_patch():
            payload = request.get_json(silent=True) or {}
            ok, errors = self.update_policy(payload)
            status = 200 if ok else 400
            return jsonify({"ok": ok, "errors": errors, "policy": self.get_policy(redacted=True)}), status

        # Preflight handler for CORS
        @app.before_request
        def handle_preflight():
            if not self._is_enabled():
                return None
            if request.method == "OPTIONS" and request.headers.get("Access-Control-Request-Method"):
                cors_enabled, cors = self._resolve_cors_for_path(request.path)
                if not cors_enabled:
                    return None
                origin = request.headers.get("Origin")
                if not origin:
                    return self._empty_204()
                if not self._origin_allowed(origin, cors):
                    return self._empty_204()
                resp = self._empty_204()
                self._apply_cors_headers(resp, cors, origin, preflight=True)
                return resp
            return None

        # Before request: generate nonce if needed
        @app.before_request
        def generate_nonce_if_needed():
            if not self._is_enabled():
                return None
            csp_conf = self._policy.get("csp", {})
            if not csp_conf.get("enabled", False):
                return None
            if csp_conf.get("add_nonce", False) and self._path_matches_any(request.path, csp_conf.get("nonce_paths", [])):
                g._csp_nonce = secrets.token_urlsafe(16)
            return None

        # After request: apply headers
        @app.after_request
        def apply_security_headers(response: Response):
            try:
                if not self._is_enabled():
                    return response
                if self._path_matches_any(request.path, self._policy.get("exclude_paths", [])):
                    return response
                # CORS
                self._maybe_apply_cors(response)
                # Standard headers
                self._apply_standard_headers(response)
                # CSP
                self._apply_csp_header(response)
                return response
            finally:
                # cleanup
                if hasattr(g, "_csp_nonce"):
                    delattr(g, "_csp_nonce")

    def get_policy(self, redacted: bool = False) -> Dict[str, Any]:
        # No secrets in policy currently; return as-is
        return deepcopy(self._policy)

    def update_policy(self, payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not isinstance(payload, dict):
            return False, ["Payload must be a JSON object"]
        # Validate to prevent header injection via newlines/semicolons
        if "csp" in payload:
            csp = payload["csp"]
            if not isinstance(csp, dict):
                errors.append("csp must be an object")
            else:
                dirs = csp.get("directives")
                if dirs is not None:
                    if not isinstance(dirs, dict):
                        errors.append("csp.directives must be an object")
                    else:
                        for k, v in dirs.items():
                            if not _valid_token(k):
                                errors.append(f"Invalid directive name: {k}")
                            if isinstance(v, list):
                                for item in v:
                                    if not _valid_value(item):
                                        errors.append(f"Invalid directive value for {k}: {item}")
                            elif isinstance(v, str):
                                if not _valid_value(v):
                                    errors.append(f"Invalid directive value for {k}: {v}")
                            elif v is not None:
                                errors.append(f"Invalid directive type for {k}")
        if "cors" in payload:
            cors = payload["cors"]
            if not isinstance(cors, dict):
                errors.append("cors must be an object")
            else:
                ao = cors.get("allowed_origins")
                if ao is not None and not (isinstance(ao, list) and all(isinstance(x, str) for x in ao)):
                    errors.append("cors.allowed_origins must be a list of strings")
                pm = cors.get("path_overrides")
                if pm is not None:
                    if not (isinstance(pm, list) and all(isinstance(x, dict) for x in pm)):
                        errors.append("cors.path_overrides must be a list of objects")
                    else:
                        for i, ov in enumerate(pm):
                            if not isinstance(ov.get("pattern"), str):
                                errors.append(f"cors.path_overrides[{i}].pattern must be a string")
        if errors:
            return False, errors

        self._policy = deep_merge(self._policy, payload)
        return True, []

    def get_suggestions(self) -> Dict[str, Any]:
        app = current_app
        cfg = self._policy
        suggestions: List[Dict[str, Any]] = []

        def add(id_: str, title: str, severity: str, details: str, action: str):
            suggestions.append({"id": id_, "title": title, "severity": severity, "details": details, "action": action})

        # Env-based suggestions
        in_prod = not app.debug and not app.testing
        if not app.config.get("SECRET_KEY"):
            add(
                "secret_key_missing",
                "SECRET_KEY is not set",
                "high",
                "Flask SECRET_KEY is missing which compromises session integrity.",
                "Set a strong, random SECRET_KEY via environment or config.",
            )
        # Cookie flags
        if not app.config.get("SESSION_COOKIE_HTTPONLY", True):
            add("cookie_httponly", "Enable HttpOnly on session cookie", "medium", "HttpOnly mitigates client-side script access to cookies.", "Set SESSION_COOKIE_HTTPONLY=True")
        if app.config.get("SESSION_COOKIE_SAMESITE") not in ("Lax", "Strict"):
            add("cookie_samesite", "Set SameSite on session cookie", "medium", "SameSite=Lax or Strict helps mitigate CSRF.", "Set SESSION_COOKIE_SAMESITE='Lax' or 'Strict'")
        if app.config.get("SESSION_COOKIE_SECURE") is not True and in_prod:
            add("cookie_secure", "Secure flag for cookies in production", "high", "Cookies should only be sent over HTTPS in production.", "Set SESSION_COOKIE_SECURE=True behind HTTPS")

        # HSTS
        hsts = cfg.get("headers", {}).get("hsts", {})
        if hsts.get("enabled", False):
            if not request.is_secure and in_prod:
                add("hsts_https", "HSTS active only over HTTPS", "low", "HSTS headers are only effective over HTTPS.", "Serve the app behind HTTPS to benefit from HSTS")
        else:
            if in_prod:
                add("hsts_disabled", "Enable HSTS in production", "medium", "HSTS helps prevent protocol downgrade and cookie hijacking.", "Enable headers.hsts.enabled and configure an appropriate max_age")

        # CORS
        cors = cfg.get("cors", {})
        if cors.get("enabled", False):
            ao = cors.get("allowed_origins", [])
            cred = cors.get("allow_credentials", False)
            if "*" in ao and cred:
                add("cors_star_credentials", "Avoid '*' with credentials", "high", "Wildcard origins cannot be used when Allow-Credentials is true.", "Enumerate trusted origins explicitly in cors.allowed_origins")
        else:
            add("cors_disabled", "CORS management disabled", "low", "If your API is used cross-origin, configure CORS explicitly.", "Enable cors.enabled and set allowed_origins")

        # CSP
        csp = cfg.get("csp", {})
        if not csp.get("enabled", False):
            add("csp_disabled", "Enable Content-Security-Policy", "high", "CSP mitigates XSS and data injection attacks.", "Enable csp.enabled and define restrictive directives")
        else:
            dirs = csp.get("directives", {})
            if dirs.get("object-src") != ["'none'"]:
                add("csp_object_src", "Set object-src 'none'", "medium", "The object-src directive should generally be 'none' to disable legacy plugins.", "Set csp.directives.object-src to ['\'none\'']")
            if "frame-ancestors" not in dirs:
                xfo = cfg.get("headers", {}).get("x_frame_options", "")
                if xfo not in ("DENY", "SAMEORIGIN"):
                    add("framing_control", "Control framing with frame-ancestors or X-Frame-Options", "medium", "Prevent clickjacking by disallowing or restricting framing.", "Set csp.directives.frame-ancestors or headers.x_frame_options")
            ss = dirs.get("script-src", [])
            if any(v in ss for v in ["'unsafe-inline'", "'unsafe-eval'"]):
                add("csp_unsafe_script", "Avoid 'unsafe-inline'/'unsafe-eval' in script-src", "high", "These weaken CSP and enable XSS vectors.", "Use nonces or hashes for inline scripts and avoid eval")
            if dirs.get("default-src") in (['*'], ["*"]):
                add("csp_default_star", "Avoid default-src '*'", "high", "A wildcard default-src is overly permissive.", "Restrict to 'self' and required origins only")
            if csp.get("report_only", False) and in_prod:
                add("csp_report_only", "CSP in report-only mode in production", "low", "Policies in report-only do not enforce restrictions.", "Disable report_only to enforce CSP")

        # Referrer-Policy
        rp = cfg.get("headers", {}).get("referrer_policy")
        if not rp or rp not in (
            "no-referrer",
            "no-referrer-when-downgrade",
            "origin",
            "origin-when-cross-origin",
            "same-origin",
            "strict-origin",
            "strict-origin-when-cross-origin",
            "unsafe-url",
        ):
            add("referrer_policy", "Set a valid Referrer-Policy", "low", "Referrer-Policy controls referrer leakage.", "Set headers.referrer_policy to a modern value like 'strict-origin-when-cross-origin'")

        # COOP/COEP/CORP
        if cfg.get("headers", {}).get("cross_origin_opener_policy") != "same-origin":
            add("coop", "Strengthen Cross-Origin-Opener-Policy", "low", "COOP 'same-origin' isolates browsing context groups.", "Set headers.cross_origin_opener_policy to 'same-origin'")
        if cfg.get("headers", {}).get("cross_origin_embedder_policy") != "require-corp":
            add("coep", "Use Cross-Origin-Embedder-Policy 'require-corp' when possible", "low", "COEP with COOP enables powerful isolation and APIs like SharedArrayBuffer.", "Set headers.cross_origin_embedder_policy to 'require-corp' where compatible")
        if cfg.get("headers", {}).get("cross_origin_resource_policy") not in ("same-site", "same-origin", "cross-origin"):
            add("corp", "Set a Cross-Origin-Resource-Policy", "low", "CORP protects resources from being loaded by other origins.", "Set headers.cross_origin_resource_policy to 'same-origin' or 'same-site'")

        return {
            "app": {
                "debug": bool(app.debug),
                "testing": bool(app.testing),
                "https_request": bool(request.is_secure),
            },
            "policy": self.get_policy(redacted=True),
            "suggestions": suggestions,
        }

    # Helpers
    def _is_enabled(self) -> bool:
        return bool(self._policy.get("enabled", True))

    def _path_matches_any(self, path: str, patterns: List[str]) -> bool:
        for p in patterns or []:
            try:
                if re.search(p, path):
                    return True
            except re.error:
                continue
        return False

    def _resolve_cors_for_path(self, path: str) -> Tuple[bool, Dict[str, Any]]:
        cors = deepcopy(self._policy.get("cors", {}))
        if not cors.get("enabled", False):
            return False, cors
        for override in cors.get("path_overrides", []) or []:
            pat = override.get("pattern")
            pol = override.get("policy") or {}
            try:
                if pat and re.search(pat, path):
                    merged = deep_merge(deepcopy(cors), pol)
                    return True, merged
            except re.error:
                continue
        return True, cors

    def _origin_allowed(self, origin: str, cors: Dict[str, Any]) -> bool:
        allowed = cors.get("allowed_origins", []) or []
        for pattern in allowed:
            if pattern == "*":
                return True
            if pattern.startswith("regex:"):
                try:
                    if re.fullmatch(pattern[len("regex:"):], origin):
                        return True
                except re.error:
                    continue
            elif "*" in pattern:
                # convert wildcard to regex
                regex = re.escape(pattern).replace(r"\*", ".*")
                if re.fullmatch(regex, origin):
                    return True
            else:
                if origin == pattern:
                    return True
        return False

    def _maybe_apply_cors(self, response: Response) -> None:
        cors_enabled, cors = self._resolve_cors_for_path(request.path)
        if not cors_enabled:
            return
        origin = request.headers.get("Origin")
        if not origin:
            return
        if not self._origin_allowed(origin, cors):
            return
        self._apply_cors_headers(response, cors, origin, preflight=False)

    def _apply_cors_headers(self, response: Response, cors: Dict[str, Any], origin: str, preflight: bool):
        allow_credentials = bool(cors.get("allow_credentials", False))
        allowed_origins = cors.get("allowed_origins", []) or []
        if "*" in allowed_origins and not allow_credentials and preflight is False:
            response.headers["Access-Control-Allow-Origin"] = "*"
        else:
            response.headers["Access-Control-Allow-Origin"] = origin
            # Vary to ensure caches differentiate by Origin
            vary = set(h.strip() for h in response.headers.get("Vary", "").split(",") if h.strip())
            vary.add("Origin")
            response.headers["Vary"] = ", ".join(sorted(vary))
        if allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        if preflight:
            methods = cors.get("allowed_methods", []) or []
            headers = cors.get("allowed_headers", []) or []
            if methods:
                response.headers["Access-Control-Allow-Methods"] = ", ".join(sorted(set(methods)))
            if headers:
                response.headers["Access-Control-Allow-Headers"] = ", ".join(sorted(set(headers)))
            max_age = cors.get("max_age")
            if isinstance(max_age, int) and max_age >= 0:
                response.headers["Access-Control-Max-Age"] = str(max_age)
        else:
            exposed = cors.get("exposed_headers", []) or []
            if exposed:
                response.headers["Access-Control-Expose-Headers"] = ", ".join(sorted(set(exposed)))

    def _apply_standard_headers(self, response: Response) -> None:
        headers_conf = self._policy.get("headers", {})
        # HSTS over HTTPS only
        hsts = headers_conf.get("hsts", {})
        if hsts.get("enabled", False) and request.is_secure:
            parts = [f"max-age={int(hsts.get('max_age', 0))}"]
            if hsts.get("include_subdomains", False):
                parts.append("includeSubDomains")
            if hsts.get("preload", False):
                parts.append("preload")
            response.headers["Strict-Transport-Security"] = "; ".join(parts)
        # X-Frame-Options
        xfo = headers_conf.get("x_frame_options")
        if xfo in ("DENY", "SAMEORIGIN"):
            response.headers["X-Frame-Options"] = xfo
        # X-Content-Type-Options
        xcto = headers_conf.get("x_content_type_options")
        if xcto == "nosniff":
            response.headers["X-Content-Type-Options"] = "nosniff"
        # Referrer-Policy
        rp = headers_conf.get("referrer_policy")
        if isinstance(rp, str) and rp:
            response.headers["Referrer-Policy"] = rp
        # Permissions-Policy
        pp = headers_conf.get("permissions_policy")
        if isinstance(pp, str) and pp:
            response.headers["Permissions-Policy"] = pp
        # COOP
        coop = headers_conf.get("cross_origin_opener_policy")
        if isinstance(coop, str) and coop:
            response.headers["Cross-Origin-Opener-Policy"] = coop
        # COEP
        coep = headers_conf.get("cross_origin_embedder_policy")
        if isinstance(coep, str) and coep:
            response.headers["Cross-Origin-Embedder-Policy"] = coep
        # CORP
        corp = headers_conf.get("cross_origin_resource_policy")
        if isinstance(corp, str) and corp:
            response.headers["Cross-Origin-Resource-Policy"] = corp

    def _apply_csp_header(self, response: Response) -> None:
        csp_conf = self._policy.get("csp", {})
        if not csp_conf.get("enabled", False):
            return
        # Compose CSP value
        directives = deepcopy(csp_conf.get("directives", {}))
        nonce = getattr(g, "_csp_nonce", None)
        if csp_conf.get("add_nonce", False) and nonce:
            # Ensure nonce is added for script-src and style-src
            for k in ("script-src", "style-src"):
                vals = directives.get(k)
                if vals is None:
                    # fall back to default-src or self
                    base = directives.get("default-src") or ["'self'"]
                    vals = list(base)
                if f"'nonce-{nonce}'" not in vals:
                    vals.append(f"'nonce-{nonce}'")
                directives[k] = vals
        # Add reporting endpoints if configured
        if csp_conf.get("report_to"):
            directives["report-to"] = [csp_conf.get("report_to")]
        if csp_conf.get("report_uri"):
            directives["report-uri"] = [csp_conf.get("report_uri")]

        csp_value = self._serialize_csp(directives)
        header_name = "Content-Security-Policy-Report-Only" if csp_conf.get("report_only", False) else "Content-Security-Policy"
        response.headers[header_name] = csp_value

    def _serialize_csp(self, directives: Dict[str, Any]) -> str:
        parts: List[str] = []
        for k, v in directives.items():
            if v is None:
                continue
            if isinstance(v, list):
                values = [str(x) for x in v]
            elif isinstance(v, str):
                values = [v]
            else:
                # flag directives like upgrade-insecure-requests with empty value
                values = []
            parts.append(f"{k} {' '.join(values)}".strip())
        return "; ".join(parts)

    def _empty_204(self) -> Response:
        resp = Response(status=204)
        resp.headers["Content-Length"] = "0"
        return resp

    # Template helper
    def get_csp_nonce(self) -> str:
        return getattr(g, "_csp_nonce", "")


# Utilities

def deep_merge(base: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = deep_merge(deepcopy(base.get(k)), v)
        else:
            base[k] = v
    return base


def _valid_token(name: str) -> bool:
    return isinstance(name, str) and bool(re.fullmatch(r"[A-Za-z0-9\-]+", name))


def _valid_value(val: str) -> bool:
    if not isinstance(val, str):
        return False
    # Disallow newlines/CR and semicolons to prevent header injection
    if any(c in val for c in ["\n", "\r", ";"]):
        return False
    return True

