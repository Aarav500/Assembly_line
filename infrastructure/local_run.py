"""Local infrastructure dashboard for development without Docker."""
from __future__ import annotations

import os
from typing import Any, Dict

import requests
from flask import Flask, jsonify, render_template_string

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Unified Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; background: #0b132b; color: #e0e0e0; }
    h1 { color: #4caf50; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
    .card { padding: 1rem; border-radius: 12px; background: #1c2541; box-shadow: 0 4px 10px rgba(0,0,0,0.25); }
    .status { font-weight: bold; }
    .ok { color: #4caf50; }
    .fail { color: #ff6b6b; }
    code { color: #c5e1a5; }
  </style>
</head>
<body>
  <h1>Unified Application Dashboard</h1>
  <p>Use this page to verify the locally launched backend and frontend health endpoints.</p>
  <div class="grid">
    {% for service in services %}
    <div class="card">
      <h2>{{ service.name }}</h2>
      <p class="status {{ 'ok' if service.ok else 'fail' }}">Status: {{ service.status }}</p>
      <p>URL: <code>{{ service.url }}</code></p>
      <pre>{{ service.details }}</pre>
    </div>
    {% endfor %}
  </div>
</body>
</html>
"""


def _fetch_health(name: str, url: str) -> Dict[str, Any]:
    endpoint = f"{url.rstrip('/')}/health"
    try:
        resp = requests.get(endpoint, timeout=2)
        resp.raise_for_status()
        payload = resp.json()
        return {
            "name": name,
            "url": endpoint,
            "ok": True,
            "status": payload.get("status", "healthy"),
            "details": payload,
        }
    except Exception as exc:  # pragma: no cover - runtime helper
        return {
            "name": name,
            "url": endpoint,
            "ok": False,
            "status": "unreachable",
            "details": str(exc),
        }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/health")
    def health() -> Any:
        services = [
            _fetch_health("backend", BACKEND_URL),
            _fetch_health("frontend", FRONTEND_URL),
        ]
        overall_ok = all(s["ok"] for s in services)
        return jsonify({"status": "healthy" if overall_ok else "degraded", "services": services}), 200

    @app.route("/")
    def dashboard() -> Any:
        services = [
            _fetch_health("backend", BACKEND_URL),
            _fetch_health("frontend", FRONTEND_URL),
        ]
        return render_template_string(DASHBOARD_HTML, services=services)

    return app


def main() -> None:
    port = int(os.environ.get("PORT", 8080))
    create_app().run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
