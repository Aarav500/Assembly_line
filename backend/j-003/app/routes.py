from flask import Blueprint, current_app, jsonify

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return jsonify(
        {
            "name": current_app.config.get(
                "PROJECT_NAME", "local-dev-environments--codespaces-templates-auto-generated-"
            ),
            "description": current_app.config.get(
                "PROJECT_DESCRIPTION",
                "Local dev environments & Codespaces templates auto-generated per project",
            ),
            "stack": current_app.config.get("PROJECT_STACK", "python,flask"),
            "version": current_app.config.get("VERSION", "0.0.0"),
            "status": "ok",
        }
    )


@bp.get("/healthz")
@bp.get("/readyz")
def health():
    return jsonify({"status": "healthy"})

