import json
from flask import Blueprint, current_app, jsonify, render_template, request
from .recommendations.engine import get_engine


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    defaults = {
        "project_name": "My Project",
        "language": "python",
        "framework": "flask",
        "cloud_provider": "aws",
        "database": "postgres",
        "expected_users": 1000,
        "traffic_spikes": False,
        "handles_pii": False,
        "compliance": [],
        "public_api": True,
        "mobile_audience": True,
        "budget_tier": "medium",
        "deployment": "container",
        "ci_cd": True,
    }
    return render_template("index.html", defaults=defaults, app_name=current_app.config.get("APP_NAME"))


def _parse_context_from_request(req):
    if req.is_json:
        payload = req.get_json(silent=True) or {}
    else:
        payload = req.form.to_dict(flat=True)
        # include non-flat booleans
        for b in ["traffic_spikes", "handles_pii", "public_api", "mobile_audience", "ci_cd"]:
            if b in req.form:
                payload[b] = True
        # arrays
        comp = req.form.getlist("compliance")
        if comp:
            payload["compliance"] = comp
    # Query string can override
    for k, v in req.args.items():
        payload.setdefault(k, v)
    return payload


@main_bp.post("/analyze")
def analyze():
    ctx = _parse_context_from_request(request)
    engine = get_engine()
    results = engine.evaluate(ctx)
    total = sum(len(v) for v in results.values())
    return render_template(
        "results.html",
        context=ctx,
        results=results,
        total=total,
        app_name=current_app.config.get("APP_NAME"),
    )


@main_bp.get("/api/recommendations")
def api_recommendations_get():
    ctx = _parse_context_from_request(request)
    engine = get_engine()
    results = engine.evaluate(ctx)
    return jsonify({
        "context": ctx,
        "recommendations": results,
        "version": current_app.config.get("APP_VERSION"),
    })


@main_bp.post("/api/recommendations")
def api_recommendations_post():
    ctx = _parse_context_from_request(request)
    engine = get_engine()
    results = engine.evaluate(ctx)
    return jsonify({
        "context": ctx,
        "recommendations": results,
        "version": current_app.config.get("APP_VERSION"),
    })


@main_bp.get("/api/docs")
def api_docs():
    example = {
        "language": "python",
        "framework": "flask",
        "cloud_provider": "aws",
        "database": "postgres",
        "expected_users": 25000,
        "traffic_spikes": True,
        "handles_pii": True,
        "compliance": ["gdpr"],
        "public_api": True,
        "mobile_audience": True,
        "budget_tier": "low",
        "deployment": "container",
        "ci_cd": True,
    }
    return render_template("api_docs.html", example=json.dumps(example, indent=2))


@main_bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@main_bp.get("/version")
def version():
    return jsonify({
        "name": current_app.config.get("APP_NAME"),
        "version": current_app.config.get("APP_VERSION"),
    })

