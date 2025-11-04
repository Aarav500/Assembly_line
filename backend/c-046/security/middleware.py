from typing import Optional
from flask import request, make_response
from .policy import CSPPolicyConfig, CORSConfig


def register_security_middleware(app):
    # Generic OPTIONS handler for CORS preflight
    @app.before_request
    def _handle_preflight():
        if request.method == 'OPTIONS':
            resp = make_response('', 204)
            _apply_cors_headers(app, resp)
            return resp

    @app.after_request
    def _apply_headers(resp):
        # CSP
        csp_dict = app.config.get('SECURITY', {}).get('CSP_POLICY')
        if csp_dict:
            try:
                csp = CSPPolicyConfig.from_dict(csp_dict)
                header_val = csp.to_header()
                if header_val:
                    resp.headers['Content-Security-Policy'] = header_val
            except Exception:
                pass

        # CORS
        _apply_cors_headers(app, resp)

        # Other security headers
        headers_cfg = (app.config.get('SECURITY') or {}).get('HEADERS') or {}

        # HSTS only on HTTPS
        if headers_cfg.get('hsts') and request.is_secure:
            # 1 year + includeSubDomains + preload (optional)
            resp.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

        if headers_cfg.get('x_content_type_options', True):
            resp.headers.setdefault('X-Content-Type-Options', 'nosniff')

        xfo = headers_cfg.get('x_frame_options')
        if xfo:
            resp.headers.setdefault('X-Frame-Options', xfo)

        ref = headers_cfg.get('referrer_policy')
        if ref:
            resp.headers.setdefault('Referrer-Policy', ref)

        perm = headers_cfg.get('permissions_policy')
        if perm:
            resp.headers.setdefault('Permissions-Policy', perm)

        coep = headers_cfg.get('coep')
        if coep:
            resp.headers.setdefault('Cross-Origin-Embedder-Policy', coep)

        coop = headers_cfg.get('coop')
        if coop:
            resp.headers.setdefault('Cross-Origin-Opener-Policy', coop)

        corp = headers_cfg.get('corp')
        if corp:
            resp.headers.setdefault('Cross-Origin-Resource-Policy', corp)

        return resp


def _apply_cors_headers(app, resp):
    cors_dict = app.config.get('SECURITY', {}).get('CORS')
    if not cors_dict:
        return resp
    try:
        cfg = CORSConfig.from_dict(cors_dict)
    except Exception:
        return resp

    origin = request.headers.get('Origin')
    allow_origin_value: Optional[str] = None

    if cfg.mode == 'public':
        # Public APIs: allow any origin; if credentials true, must reflect origin
        if cfg.allow_credentials and origin:
            allow_origin_value = origin
        else:
            allow_origin_value = '*'
    elif cfg.mode == 'allowlist':
        if origin and origin in (cfg.allow_origins or []):
            allow_origin_value = origin
    else:  # strict
        # Only same-origin allowed (omit header entirely)
        allow_origin_value = None

    if allow_origin_value:
        resp.headers['Access-Control-Allow-Origin'] = allow_origin_value
        # Ensure Vary: Origin for dynamic reflection
        vary = resp.headers.get('Vary')
        if vary:
            if 'Origin' not in vary:
                resp.headers['Vary'] = f"{vary}, Origin"
        else:
            resp.headers['Vary'] = 'Origin'

        # Credentials
        if cfg.allow_credentials:
            resp.headers['Access-Control-Allow-Credentials'] = 'true'

        # Methods
        allow_methods = ', '.join(sorted(set(cfg.allow_methods or [])))
        if allow_methods:
            resp.headers['Access-Control-Allow-Methods'] = allow_methods

        # Request headers
        req_headers = request.headers.get('Access-Control-Request-Headers')
        if req_headers:
            resp.headers['Access-Control-Allow-Headers'] = req_headers
        else:
            allow_headers = ', '.join(sorted(set(cfg.allow_headers or [])))
            if allow_headers:
                resp.headers['Access-Control-Allow-Headers'] = allow_headers

        # Expose headers
        if cfg.expose_headers:
            resp.headers['Access-Control-Expose-Headers'] = ', '.join(sorted(set(cfg.expose_headers)))

        # Max age (preflight cache)
        if cfg.max_age:
            resp.headers['Access-Control-Max-Age'] = str(int(cfg.max_age))

    return resp

