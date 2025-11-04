import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from flask import Response
from registry import ProjectRegistry
from analyzer import Analyzer
from config import DATA_DIR

app = Flask(__name__)
registry = ProjectRegistry(os.path.join(DATA_DIR, "projects.json"))
analyzer = Analyzer()


@app.route("/api/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/api/projects", methods=["GET"]) 
def list_projects():
    projects = registry.list_projects()
    return jsonify({"projects": projects})


@app.route("/api/projects", methods=["POST"]) 
def add_project():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    path = data.get("path")
    if not name or not path:
        return jsonify({"error": "name and path are required"}), 400
    try:
        project = registry.add_project(name=name, path=path)
        return jsonify({"project": project}), 201
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/projects/<project_id>", methods=["DELETE"]) 
def delete_project(project_id: str):
    try:
        registry.remove_project(project_id)
        return Response(status=204)
    except KeyError:
        return jsonify({"error": "project not found"}), 404


@app.route("/api/insights/scan", methods=["GET"]) 
def scan_all():
    mode = request.args.get("mode", "full")
    projects = registry.list_projects()
    report = analyzer.scan_projects(projects, mode=mode)
    return jsonify(report)


@app.route("/api/insights/duplicates", methods=["GET"]) 
def duplicates():
    dtype = request.args.get("type", "all")
    projects = registry.list_projects()
    report = analyzer.scan_projects(projects)
    out = {}
    if dtype in ("all", "exact"):
        out["exact_duplicates"] = report.get("exact_duplicates", [])
    if dtype in ("all", "near"):
        out["near_duplicate_clusters"] = report.get("near_duplicate_clusters", [])
    return jsonify(out)


@app.route("/api/insights/shared-components", methods=["GET"]) 
def shared_components():
    projects = registry.list_projects()
    report = analyzer.scan_projects(projects)
    return jsonify(report.get("shared_components", {}))


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app
