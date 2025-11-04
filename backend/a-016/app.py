import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify, render_template

from reverse_manifest.detectors.python_detector import PythonDetector
from reverse_manifest.detectors.docker_detector import DockerDetector
from reverse_manifest.detectors.generic_detector import GenericDetector


def generate_manifest(root_path: str) -> dict:
    python_info = PythonDetector().detect(root_path)
    docker_info = DockerDetector().detect(root_path)
    generic_info = GenericDetector().detect(root_path)

    languages = sorted(set(generic_info.get("languages", []) + python_info.get("languages", [])))
    frameworks = sorted(set(generic_info.get("frameworks", []) + python_info.get("frameworks", [])))

    manifest = {
        "project": {
            "name": generic_info.get("project_name"),
            "description": generic_info.get("description"),
            "license": generic_info.get("license"),
        },
        "detected": {
            "languages": languages,
            "frameworks": frameworks,
            "imported_modules": python_info.get("imports", []),
        },
        "runtime": {
            "python_version": python_info.get("python_version"),
            "base_image": docker_info.get("dockerfile", {}).get("base_image"),
        },
        "dependencies": {
            "python": {
                "default": python_info.get("dependencies", {}).get("default", {}),
                "dev": python_info.get("dependencies", {}).get("dev", {}),
            }
        },
        "entrypoints": {
            "web": python_info.get("entrypoint") or docker_info.get("dockerfile", {}).get("cmd")
        },
        "ports": {
            "app": python_info.get("port"),
            "docker": docker_info.get("dockerfile", {}).get("exposed_ports") or docker_info.get("compose", {}).get("ports")
        },
        "docker": docker_info,
        "services": docker_info.get("compose", {}).get("services"),
        "env": generic_info.get("env"),
        "tests": generic_info.get("tests"),
        "files": {
            "readme": generic_info.get("readme_path"),
            "license": generic_info.get("license_path"),
            "requirements": python_info.get("requirements_paths", []),
            "pyproject": python_info.get("pyproject_path"),
            "pipfile": python_info.get("pipfile_path"),
            "dockerfile": docker_info.get("dockerfile", {}).get("path"),
            "compose": docker_info.get("compose", {}).get("path"),
        },
        "generated_at": GenericDetector.now_iso(),
        "root": os.path.abspath(root_path),
        "version": 1
    }

    # Persist manifest at root
    out_path = os.path.join(root_path, "reverse_manifest.json")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        manifest["_output_file"] = out_path
    except Exception as e:
        manifest["_error_writing_manifest"] = str(e)

    return manifest


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/reverse-manifest")
    def reverse_manifest():
        data = request.get_json(silent=True) or {}
        root_path = data.get("path") or os.environ.get("SCAN_ROOT") or os.getcwd()
        manifest = generate_manifest(root_path)
        return jsonify(manifest)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5057"))
    app = create_app()
    app.run(host="0.0.0.0", port=port)

