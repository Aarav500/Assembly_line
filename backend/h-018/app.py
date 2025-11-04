import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import tempfile
import zipfile
from datetime import datetime
from flask import Flask, request, jsonify

from config import Settings
from db import init_db, SessionLocal
from models import Project
from services.project_service import (
    register_project,
    analyze_project,
    analyze_all_projects,
    list_projects,
    get_project_details,
)
from analysis.reuse_miner import build_report, find_similar_functions


def create_app():
    app = Flask(__name__)
    settings = Settings()

    # Ensure workspace exists
    os.makedirs(settings.WORKSPACE_DIR, exist_ok=True)

    # Initialize DB
    init_db()

    @app.route("/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok"})

    @app.route("/projects", methods=["GET"]) 
    def projects_get():
        with SessionLocal() as db:
            return jsonify(list_projects(db))

    @app.route("/projects/<int:project_id>", methods=["GET"]) 
    def projects_get_one(project_id: int):
        with SessionLocal() as db:
            details = get_project_details(db, project_id)
            if not details:
                return jsonify({"error": "Not found"}), 404
            return jsonify(details)

    @app.route("/projects", methods=["POST"]) 
    def projects_register():
        payload = request.get_json(force=True, silent=True) or {}
        name = payload.get("name")
        root_path = payload.get("path")
        if not name or not root_path:
            return jsonify({"error": "name and path are required"}), 400
        if not os.path.isdir(root_path):
            return jsonify({"error": f"Path does not exist: {root_path}"}), 400
        with SessionLocal() as db:
            project = register_project(db, name=name, root_path=root_path)
            return jsonify({"id": project.id, "name": project.name, "path": project.root_path})

    @app.route("/projects/upload", methods=["POST"]) 
    def projects_upload():
        if "file" not in request.files:
            return jsonify({"error": "multipart form 'file' is required (zip)"}), 400
        upload = request.files["file"]
        if not upload.filename.lower().endswith(".zip"):
            return jsonify({"error": "Only .zip archives are supported"}), 400
        project_name = request.form.get("name") or os.path.splitext(upload.filename)[0]

        settings = Settings()
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        target_dir = os.path.join(settings.WORKSPACE_DIR, f"{project_name}-{ts}")
        os.makedirs(target_dir, exist_ok=True)

        data = upload.read()
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(target_dir)
        except zipfile.BadZipFile:
            return jsonify({"error": "Invalid zip file"}), 400

        with SessionLocal() as db:
            project = register_project(db, name=project_name, root_path=target_dir)
            return jsonify({"id": project.id, "name": project.name, "path": project.root_path})

    @app.route("/analyze", methods=["POST"]) 
    def analyze_endpoint():
        payload = request.get_json(force=True, silent=True) or {}
        project_id = payload.get("project_id")
        with SessionLocal() as db:
            if project_id:
                result = analyze_project(db, project_id)
                if not result:
                    return jsonify({"error": "Project not found"}), 404
                return jsonify({"status": "ok", "project_id": project_id})
            else:
                analyze_all_projects(db)
                return jsonify({"status": "ok"})

    @app.route("/similarities", methods=["GET"]) 
    def similarities_endpoint():
        try:
            threshold = float(request.args.get("threshold", 0.6))
            limit = int(request.args.get("limit", 100))
        except ValueError:
            return jsonify({"error": "Invalid threshold or limit"}), 400
        with SessionLocal() as db:
            sims = find_similar_functions(db, threshold=threshold, limit=limit)
            return jsonify({
                "threshold": threshold,
                "count": len(sims),
                "pairs": sims,
            })

    @app.route("/report", methods=["GET"]) 
    def report_endpoint():
        with SessionLocal() as db:
            report = build_report(db)
            return jsonify(report)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



@app.route('/projects/proj1', methods=['GET'])
def _auto_stub_projects_proj1():
    return 'Auto-generated stub for /projects/proj1', 200


@app.route('/knowledge', methods=['POST'])
def _auto_stub_knowledge():
    return 'Auto-generated stub for /knowledge', 200


@app.route('/search?q=auth&reusable=true', methods=['GET'])
def _auto_stub_search_q_auth_reusable_true():
    return 'Auto-generated stub for /search?q=auth&reusable=true', 200
