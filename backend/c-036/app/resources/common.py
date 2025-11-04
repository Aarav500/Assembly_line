from flask import Blueprint, jsonify, current_app

bp = Blueprint('common', __name__)


@bp.get('/health')
def health():
    return jsonify({"status": "ok"})


@bp.get('/docs')
def docs():
    return jsonify({
        "name": "Example API",
        "versioning": {
            "default_version": current_app.config['DEFAULT_API_VERSION'],
            "supported_versions": current_app.config['SUPPORTED_VERSIONS'],
            "negotiation": {
                "url_path": "/api/{version}/...",
                "query_param": "?version=v2 or ?v=2",
                "headers": {
                    "X-API-Version": "2 or v2",
                    "Accept": [
                        "application/vnd.{vendor}+json; version=2",
                        "application/vnd.{vendor}.v2+json"
                    ]
                }
            },
            "backward_compatibility": {
                "adapters": "Older versions are adapted from latest canonical model",
                "deprecation_headers": [
                    "Deprecation: true",
                    "Sunset: <date>",
                    "Link: <deprecation-doc>; rel=deprecation",
                    "Warning: 299 - \"Deprecated API version\""
                ]
            }
        },
        "endpoints": {
            "v1": ["GET /api/v1/users", "GET /api/v1/users/{id}", "POST /api/v1/users"],
            "v2": ["GET /api/v2/users", "GET /api/v2/users/{id}", "POST /api/v2/users"],
            "negotiated": ["GET /api/users", "POST /api/users"]
        }
    })

