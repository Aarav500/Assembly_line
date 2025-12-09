"""Lightweight frontend control plane to surface backend status."""
from __future__ import annotations

import os
from typing import Any

import requests
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

BACKEND_URL = os.environ.get("BACKEND_API_URL", "http://backend:5000")
INFRA_URL = os.environ.get("INFRA_URL", "http://infrastructure:8080")

PAGE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Unified App Control Plane</title>
    <style>
      body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 32px; background: #0b1021; color: #f5f7ff; }
      h1 { margin: 0 0 12px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 24px; }
      .card { background: #11172f; border: 1px solid #1f2a4a; padding: 16px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.35); }
      .label { color: #8ea2d6; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
      .value { font-size: 22px; margin: 6px 0 12px; font-weight: 700; }
      a { color: #80d6ff; }
      pre { background: #0d1329; border: 1px solid #1f2a4a; border-radius: 8px; padding: 12px; overflow-x: auto; color: #9fe8a8; }
      .status-ok { color: #7ee18d; }
      .status-fail { color: #ff9f7a; }
    </style>
  </head>
  <body>
    <h1>Unified App Control Plane</h1>
    <p>Use this page as the landing entry to reach the API, dashboard, and health checks.</p>

    <div class="grid">
      <div class="card">
        <div class="label">Backend API</div>
        <div class="value status-{{ 'ok' if backend.get('status') == 'healthy' else 'fail' }}">{{ backend_status }}</div>
        <p><strong>Modules:</strong> {{ backend.get('venv_info', {}).get('total_modules', 0) }}</p>
        <p><strong>VEnvs:</strong> {{ backend.get('venv_info', {}).get('total_venvs', 0) }}</p>
        <p><a href="{{ api_url }}" target="_blank">Open API via nginx (/api/)</a></p>
      </div>

      <div class="card">
        <div class="label">Infrastructure Dashboard</div>
        <div class="value status-{{ 'ok' if infra_ok else 'fail' }}">{{ 'Healthy' if infra_ok else 'Unavailable' }}</div>
        <p><a href="{{ infra_browser }}" target="_blank">Open dashboard</a></p>
      </div>

      <div class="card">
        <div class="label">Raw Health Data</div>
        <pre>{{ backend | tojson(indent=2) }}</pre>
      </div>
    </div>
  </body>
</html>
"""

def fetch_json(url: str) -> dict[str, Any]:
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 - we only surface availability to the UI
        return {}


@app.route("/")
def index():
    backend = fetch_json(f"{BACKEND_URL}/health")
    backend_status = backend.get("status", "unreachable")
    infra_resp = fetch_json(f"{INFRA_URL}/health")
    infra_ok = infra_resp.get("status") == "healthy"

    # nginx exposes API under /api/
    api_url = os.environ.get("PUBLIC_API_URL") or "/api/"
    infra_browser = os.environ.get("PUBLIC_INFRA_URL") or "/infra/"

    return render_template_string(
        PAGE,
        backend=backend,
        backend_status=backend_status.title(),
        infra_ok=infra_ok,
        api_url=api_url,
        infra_browser=infra_browser,
    )


@app.route("/health")
def health():
    backend = fetch_json(f"{BACKEND_URL}/health")
    return jsonify({
        "status": "healthy",
        "service": "frontend",
        "backend": backend,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
