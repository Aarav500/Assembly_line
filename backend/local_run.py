"""Local backend launcher mirroring container health server."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify

BASE_DIR = Path(__file__).resolve().parent
MAPPING_PATH = BASE_DIR / "venv_mapping.json"


def _load_mapping() -> Dict[str, Any]:
    if MAPPING_PATH.exists():
        try:
            with MAPPING_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:  # pragma: no cover - defensive
            return {"error": str(exc)}
    return {}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index() -> Any:
        base_url = os.environ.get("VM_PUBLIC_IP") or "localhost"
        return (
            jsonify(
                {
                    "message": "Backend control plane is running",
                    "next_steps": [
                        "Use /health to verify container status",
                        "Use /modules to inspect per-module virtual environments",
                        f"Access the nginx entrypoint on http://{base_url}/ for the dashboard/front-end",
                        "If you intended to hit the API, prefix your path with /api/ when using nginx",
                    ],
                }
            ),
            200,
        )

    @app.route("/health")
    def health() -> Any:
        data = _load_mapping()
        venv_modules = data.get("venv_modules", {}) if isinstance(data, dict) else {}
        venv_requirements = data.get("venv_requirements", {}) if isinstance(data, dict) else {}
        module_map = data.get("module_venv_map", {}) if isinstance(data, dict) else {}

        venv_info = {
            "total_venvs": len(venv_requirements),
            "total_modules": len(module_map),
            "venvs": {
                name: {
                    "module_count": len(modules),
                    "modules": modules[:5],
                }
                for name, modules in venv_modules.items()
            },
        }
        if isinstance(data, dict) and "error" in data:
            venv_info["error"] = data["error"]

        return (
            jsonify(
                {
                    "status": "healthy",
                    "service": "backend",
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "venv_info": venv_info,
                }
            ),
            200,
        )

    @app.route("/modules")
    def modules() -> Any:
        mapping = _load_mapping()
        if mapping:
            return jsonify(mapping), 200
        return jsonify({"error": "No mapping found"}), 404

    return app


def main() -> None:
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
