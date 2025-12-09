"""Infra dashboard showing live service health and module counts."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:5000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://frontend:3000")
PUBLIC_HOST = os.environ.get("VM_PUBLIC_IP", "localhost")
PUBLIC_INFRA_URL = os.environ.get("PUBLIC_INFRA_URL", "/infra/")
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "/api/")

TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Infrastructure Dashboard</title>
    <style>
      body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 28px; background: #0c1424; color: #e8eefc; }
      h1 { margin-top: 0; }
      .services { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 20px; }
      .card { background: #111c33; border: 1px solid #1b2c4f; padding: 16px; border-radius: 10px; }
      .label { color: #8aa7e6; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
      .value { font-size: 22px; font-weight: 700; margin: 6px 0 10px; }
      .ok { color: #7ae89f; }
      .warn { color: #ffc875; }
      a { color: #7ad1ff; }
      ul { padding-left: 18px; }
    </style>
  </head>
  <body>
    <h1>Infrastructure Dashboard</h1>
    <p>External entrypoint: <a href="http://{{ public_host }}/" target="_blank">http://{{ public_host }}/</a> (frontend)</p>
    <div class="services">
      {% for svc in services %}
      <div class="card">
        <div class="label">{{ svc.name }}</div>
        <div class="value {{ 'ok' if svc.status == 'healthy' else 'warn' }}">{{ svc.status.title() }}</div>
        <p><strong>Health:</strong> <a href="{{ svc.external }}" target="_blank">{{ svc.external }}</a></p>
        <p><strong>Modules:</strong> {{ svc.modules }} | <strong>VEnvs:</strong> {{ svc.venvs }}</p>
        {% if svc.venv_details %}
        <p><strong>VEnv breakdown</strong></p>
        <ul>
          {% for venv, count in svc.venv_details.items() %}
          <li>{{ venv }}: {{ count }} modules</li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
      {% endfor %}
    </div>
    <p style="margin-top:24px;color:#8aa7e6;">Updated {{ timestamp }} | API via {{ public_api }} | Infra via {{ public_infra }}</p>
  </body>
</html>
"""


def fetch_json(url: str) -> dict[str, Any]:
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001
        return {}


def read_mapping(component: str) -> dict[str, Any]:
    mapping_path = BASE_DIR.parent / component / "venv_mapping.json"
    if mapping_path.exists():
        try:
            with mapping_path.open() as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "infrastructure"})


@app.route("/")
def dashboard():
    services = []
    for svc_name, internal_url, external_path, mapping_target in [
        ("Backend", BACKEND_URL, f"http://{PUBLIC_HOST}/api/health", "backend"),
        ("Frontend", FRONTEND_URL, f"http://{PUBLIC_HOST}/", "frontend"),
        ("Infrastructure", "http://localhost:8080", f"http://{PUBLIC_HOST}/infra/", "infrastructure"),
    ]:
        health_data = fetch_json(f"{internal_url}/health")
        mapping = read_mapping(mapping_target)
        venvs = mapping.get("venv_requirements", {})
        venv_modules = mapping.get("venv_modules", {})
        services.append(
            {
                "name": svc_name,
                "status": health_data.get("status", "unknown"),
                "modules": len(mapping.get("module_venv_map", {})),
                "venvs": len(venvs),
                "venv_details": {k: len(v) for k, v in venv_modules.items()},
                "external": external_path,
            }
        )

    return render_template_string(
        TEMPLATE,
        services=services,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        public_host=PUBLIC_HOST,
        public_api=PUBLIC_API_URL,
        public_infra=PUBLIC_INFRA_URL,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
