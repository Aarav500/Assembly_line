"""
Main application routes (HTTP endpoints) grouped in a Blueprint.

Developer explanation:
- Blueprints help organize related endpoints and make it easier to reuse or mount them under prefixes.
- Keep route logic small; delegate heavy lifting to service/helper functions for testability.
- Responses are consistently JSON; use a helper to keep shapes uniform in larger apps.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, current_app, jsonify, request

# Create a blueprint named 'main'. You can register multiple blueprints for modular APIs.
main_bp = Blueprint("main", __name__)


@main_bp.get("/health")
def health() -> Any:
    """
    Lightweight liveness endpoint.

    Returns a JSON object indicating the app is running.

    Developer notes:
    - Keep this handler fast and side-effect free so orchestrators (e.g., Docker, K8s) can
      probe it frequently without causing load.
    - Add more checks (DB connectivity, cache ping) to /healthz or /ready if needed.
    """
    payload: Dict[str, Any] = {
        "status": "ok",
        "service": "generate-code-comments-and-developer-explanations-inline-for",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    # Optional: include debug metadata in non-production to help developers.
    if current_app.config.get("INCLUDE_DEBUG_META"):
        payload["meta"] = {
            "environment": current_app.config.get("ENV"),
            "debug": current_app.config.get("DEBUG"),
        }

    return jsonify(payload), 200


@main_bp.post("/echo")
def echo() -> Any:
    """
    Echo endpoint to demonstrate request parsing and JSON responses.

    Developer notes:
    - Shows how to get JSON from the request and return structured output with validation.
    - In a real app, validate inputs thoroughly (schema validation libraries can help).
    """
    # Get JSON body; if invalid or missing, Flask returns None.
    data = request.get_json(silent=True) or {}

    # Example of simple validation: ensure 'message' is a string if present.
    message = data.get("message")
    if message is not None and not isinstance(message, str):
        return jsonify({
            "error": {
                "code": "invalid_request",
                "message": "'message' must be a string if provided",
            }
        }), 400

    response = {
        "received": data,
        "note": "This endpoint echos your JSON payload for debugging/demo purposes.",
    }

    return jsonify(response), 200


@main_bp.get("/")
def index() -> Any:
    """
    Welcome endpoint with brief documentation.

    Developer notes:
    - Minimal inline docs help consumers discover available endpoints quickly.
    - For larger APIs, generate OpenAPI/Swagger and serve docs under /docs.
    """
    return jsonify({
        "service": "generate-code-comments-and-developer-explanations-inline-for",
        "description": "Sample Flask service with inline code comments and developer explanations.",
        "endpoints": {
            "GET /": "Service overview",
            "GET /health": "Liveness probe",
            "POST /echo": "Echo back posted JSON payload",
        },
    }), 200

