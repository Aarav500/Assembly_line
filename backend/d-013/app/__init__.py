import os
from flask import Flask, jsonify, request, current_app
from config.loader import load_config
from app.policy import PolicyManager, RateLimiter
from app.routes import main_bp


def create_app(env: str | None = None) -> Flask:
    env = env or os.getenv("APP_ENV", "dev").lower()

    cfg = load_config(env)

    app = Flask(__name__)

    # Apply app config overlay
    app.config.update(cfg.get("app", {}))
    app.config["APP_ENV"] = env

    # Initialize policy manager
    policy = PolicyManager(cfg.get("policy", {}))
    app.extensions["policy"] = policy

    # Initialize rate limiter
    limiter = RateLimiter(
        max_requests=policy.rate_limit_requests,
        window_seconds=policy.rate_limit_window,
        enabled=policy.rate_limit_enabled,
    )
    app.extensions["rate_limiter"] = limiter

    # Register blueprints
    app.register_blueprint(main_bp)

    @app.before_request
    def enforce_rate_limit():
        # Skip preflight and health checks
        if request.method == "OPTIONS":
            return None
        if request.endpoint in {"main.health"}:
            return None

        limiter = current_app.extensions["rate_limiter"]
        policy = current_app.extensions["policy"]
        if not limiter.enabled:
            return None

        # Identify requester by API key when present and valid; otherwise by IP
        identity = None
        api_key = request.headers.get(policy.auth_header)
        if api_key and policy.validate_api_key(api_key):
            identity = f"key:{api_key[:6]}"
        else:
            # X-Forwarded-For could be considered in real deployments
            identity = f"ip:{request.remote_addr}"

        key = f"{identity}:{request.endpoint or request.path}"
        allowed, retry_after = limiter.hit(key)
        if not allowed:
            resp = jsonify({
                "error": "rate_limited",
                "message": "Too many requests",
                "retry_after": retry_after,
            })
            resp.status_code = 429
            if retry_after is not None:
                resp.headers["Retry-After"] = str(int(retry_after))
            return resp
        return None

    @app.after_request
    def apply_cors_headers(response):
        policy = current_app.extensions["policy"]
        origin = request.headers.get("Origin")
        if origin and policy.is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = (response.headers.get("Vary", "") + ", Origin").strip(", ")
            response.headers["Access-Control-Allow-Credentials"] = "false"
            allow_headers = {"Content-Type", "Authorization", "X-Requested-With", policy.auth_header}
            response.headers["Access-Control-Allow-Headers"] = ", ".join(sorted(allow_headers))
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        # Basic security hardening headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    return app

