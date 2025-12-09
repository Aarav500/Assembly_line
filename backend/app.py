"""Simple backend API for unified app control plane."""
from __future__ import annotations

from pathlib import Path
import json
import os
from flask import Flask, jsonify

app = Flask(__name__)

BASE_PATH = Path(__file__).parent
MAPPING_FILE = BASE_PATH / "venv_mapping.json"

def _load_mapping() -> dict:
    if MAPPING_FILE.exists():
        try:
            with MAPPING_FILE.open() as f:
                return json.load(f)
        except Exception as exc:  # noqa: BLE001 - bubble message to operators
            return {"error": str(exc)}
    return {}


@app.route("/")
def index():
    base_url = os.environ.get("VM_PUBLIC_IP", "localhost")
    return jsonify(
        {
            "message": "Backend service is online",
            "next_steps": [
                "Use /health to verify container status",
                "Use /modules to inspect per-module virtual environments",
                "Use the frontend at http://%s/ to interact with the stack" % base_url,
                "If calling the API through nginx, prefix with /api/",
            ],
        }
    )


@app.route("/health")
def health():
    mapping = _load_mapping()
    venv_info = {
        "total_venvs": 0,
        "total_modules": 0,
        "venvs": {},
    }

    if mapping:
        venv_requirements = mapping.get("venv_requirements", {})
        venv_modules = mapping.get("venv_modules", {})
        venv_info["total_venvs"] = len(venv_requirements)
        venv_info["total_modules"] = len(mapping.get("module_venv_map", {}))
        for venv_name, modules in venv_modules.items():
            venv_info["venvs"][venv_name] = {
                "module_count": len(modules),
                "modules": modules[:5],
            }

    return jsonify({
        "status": "healthy",
        "service": "backend",
        "venv_info": venv_info,
    })


@app.route("/modules")
def list_modules():
    mapping = _load_mapping()
    if mapping:
        return jsonify(mapping)
    return jsonify({"error": "No mapping found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
