import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, g
from storage.redis_client import get_redis
from config import init_default_data, ADMIN_API_KEY
from routes.api import api_bp
from routes.admin import admin_bp
from services.users import get_user_by_api_key, get_user
from services.tiers import get_tier
from services.rate_limiter import check_and_increment
from services.usage import precheck_hard_quota, increment_and_handle


def create_app():
    app = Flask(__name__)

    # Initialize config data in Redis
    init_default_data()

    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def authenticate_and_limit():
        path = request.path
        # Admin endpoints secured via admin key
        if path.startswith('/v1/admin'):
            admin_key = request.headers.get('X-Admin-Key')
            if admin_key != ADMIN_API_KEY:
                return jsonify({"error": "admin unauthorized"}), 401
            return None

        # Only protect versioned API endpoints
        if path.startswith('/v1'):
            api_key = request.headers.get('X-API-Key')
            user = get_user_by_api_key(api_key)
            if not user:
                return jsonify({"error": "unauthorized"}), 401
            g.user = user
            tier_name = user.get('tier')
            tier = get_tier(tier_name)
            if not tier:
                return jsonify({"error": f"tier '{tier_name}' not found"}), 500
            g.tier = tier

            # Enforce hard monthly quota before processing
            allowed, quota_headers = precheck_hard_quota(user['id'], tier)
            for k, v in quota_headers.items():
                # Will be added in after_request if we proceed, or in immediate response below
                pass
            if not allowed:
                resp = jsonify({"error": "monthly quota exceeded", "detail": quota_headers})
                resp.status_code = 429
                for k, v in quota_headers.items():
                    resp.headers[k] = v
                return resp

            # Rate limiting per-second and per-minute based on tier
            rps = int(tier.get('rps') or 0)
            rpm = int(tier.get('rpm') or 0)
            allowed, headers, reason = check_and_increment(user['id'], rps=rps, rpm=rpm)
            if not allowed:
                resp = jsonify({"error": "rate limit exceeded", "reason": reason})
                resp.status_code = 429
                for k, v in headers.items():
                    resp.headers[k] = v
                # also attach quota headers
                for k, v in quota_headers.items():
                    resp.headers[k] = v
                return resp

            # Stash headers to add later
            g.rate_headers = headers
            g.quota_headers = quota_headers
        return None

    @app.after_request
    def track_usage(response):
        path = request.path
        if path.startswith('/v1') and not path.startswith('/v1/admin'):
            # Attach rate and quota headers even on errors
            for hdrs_name in ['rate_headers', 'quota_headers']:
                hdrs = getattr(g, hdrs_name, None)
                if hdrs:
                    for k, v in hdrs.items():
                        response.headers[k] = v

            # Count usage only for successful responses (<500) and non-OPTIONS
            if response.status_code < 500 and request.method != 'OPTIONS':
                user = getattr(g, 'user', None)
                tier = getattr(g, 'tier', None)
                if user and tier:
                    stats = increment_and_handle(user, tier)
                    # Refresh quota headers based on post-increment state
                    response.headers['X-Quota-Limit-Month'] = str(stats.get('quota') or 0)
                    response.headers['X-Quota-Used-Month'] = str(stats.get('usage') or 0)
                    remaining = (stats.get('quota') or 0) - (stats.get('usage') or 0)
                    response.headers['X-Quota-Remaining-Month'] = str(max(0, remaining))
        return response

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')))

