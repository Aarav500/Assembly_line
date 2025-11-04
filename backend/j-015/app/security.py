from flask import request


def apply_security_headers(response, config):
    # Basic hardening
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", config.get("REFERRER_POLICY", "no-referrer"))
    response.headers.setdefault("X-XSS-Protection", "0")  # modern browsers ignore; CSP preferred

    # CSP
    csp = config.get("CONTENT_SECURITY_POLICY")
    if csp:
        response.headers.setdefault("Content-Security-Policy", csp)

    # Permissions-Policy
    pp = config.get("PERMISSIONS_POLICY")
    if pp:
        response.headers.setdefault("Permissions-Policy", pp)

    # HSTS only on HTTPS
    if config.get("ENABLE_HSTS") and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            f"max-age={int(config.get('HSTS_MAX_AGE', 31536000))}; includeSubDomains; preload",
        )

    return response

