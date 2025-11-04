import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
import tempfile
import zipfile
import json
import uuid as uuidlib
from datetime import datetime, timezone
from typing import List, Dict

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import Config
from db import db
from models import Project
from utils.fs_utils import ensure_dir, iter_relative_files, safe_join, is_subpath
from utils.hash_utils import sha256_file, sha256_bytes

APP_NAME = "ExportImportService"
APP_VERSION = "1.0.0"


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    ensure_dir(app.config["STORAGE_DIR"])  # Ensure base storage dir exists
    ensure_dir(os.path.dirname(app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")))

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large"}), 413

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "app": APP_NAME, "version": APP_VERSION})

    @app.route("/projects", methods=["POST"])
    def create_project():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        description = data.get("description") or ""
        metadata = data.get("metadata") or {}
        p = Project(
            uuid=str(uuidlib.uuid4()),
            name=name,
            description=description,
            metadata=metadata,
        )
        db.session.add(p)
        db.session.commit()

        ensure_dir(project_files_dir(app, p))

        return jsonify(project_to_dict(p)), 201

    @app.route("/projects", methods=["GET"])
    def list_projects():
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return jsonify([project_to_dict(p) for p in projects])

    @app.route("/projects/<string:project_id>", methods=["GET"])
    def get_project(project_id):
        p = Project.query.filter((Project.uuid == project_id) | (Project.id == project_id)).first()
        if not p:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(project_to_dict(p))

    @app.route("/projects/<string:project_id>", methods=["DELETE"])
    def delete_project(project_id):
        p = Project.query.filter((Project.uuid == project_id) | (Project.id == project_id)).first()
        if not p:
            return jsonify({"error": "Project not found"}), 404

        # Remove files from storage
        files_dir = project_files_dir(app, p)
        if os.path.isdir(files_dir):
            for root, dirs, files in os.walk(files_dir, topdown=False):
                for f in files:
                    try:
                        os.remove(os.path.join(root, f))
                    except OSError:
                        pass
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except OSError:
                        pass
            try:
                os.rmdir(files_dir)
            except OSError:
                pass

        db.session.delete(p)
        db.session.commit()
        return jsonify({"status": "deleted"})

    @app.route("/projects/<string:project_id>/files", methods=["POST"])
    def upload_files(project_id):
        p = Project.query.filter((Project.uuid == project_id) | (Project.id == project_id)).first()
        if not p:
            return jsonify({"error": "Project not found"}), 404

        if 'files' not in request.files:
            return jsonify({"error": "No files part in the request. Use multipart/form-data with key 'files'"}), 400

        files = request.files.getlist('files')
        paths = request.form.getlist('path')  # optional corresponding paths

        saved = []
        base_dir = project_files_dir(app, p)
        ensure_dir(base_dir)

        for idx, fs in enumerate(files):
            if not fs.filename:
                continue
            rel_path = None
            if idx < len(paths) and paths[idx]:
                rel_path = paths[idx]
            else:
                rel_path = secure_filename(fs.filename)

            # Sanitize and ensure within base
            rel_path = rel_path.strip().lstrip("/\\")
            if not rel_path or rel_path.endswith('/') or rel_path.endswith('\\'):
                return jsonify({"error": f"Invalid path: {rel_path}"}), 400

            dest_path = safe_join(base_dir, rel_path)
            if not dest_path or not is_subpath(dest_path, base_dir):
                return jsonify({"error": f"Invalid or unsafe path: {rel_path}"}), 400

            ensure_dir(os.path.dirname(dest_path))
            fs.save(dest_path)
            saved.append({
                "path": rel_path,
                "size": os.path.getsize(dest_path),
                "sha256": sha256_file(dest_path),
            })

        return jsonify({"saved": saved, "count": len(saved)})

    @app.route("/projects/<string:project_id>/files", methods=["GET"])
    def list_project_files(project_id):
        p = Project.query.filter((Project.uuid == project_id) | (Project.id == project_id)).first()
        if not p:
            return jsonify({"error": "Project not found"}), 404
        base_dir = project_files_dir(app, p)
        files = []
        for rel_path in iter_relative_files(base_dir):
            abs_path = os.path.join(base_dir, rel_path)
            files.append({
                "path": rel_path,
                "size": os.path.getsize(abs_path),
                "sha256": sha256_file(abs_path),
            })
        return jsonify(files)

    @app.route("/projects/<string:project_id>/export", methods=["GET"])
    def export_project(project_id):
        p = Project.query.filter((Project.uuid == project_id) | (Project.id == project_id)).first()
        if not p:
            return jsonify({"error": "Project not found"}), 404

        base_dir = project_files_dir(app, p)
        files_info = []
        for rel_path in iter_relative_files(base_dir):
            abs_path = os.path.join(base_dir, rel_path)
            files_info.append({
                "path": f"files/{rel_path}",
                "size": os.path.getsize(abs_path),
                "sha256": sha256_file(abs_path),
            })

        manifest = build_manifest(p, files_info)
        metadata = p.metadata or {}

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            zf.writestr("metadata.json", json.dumps(metadata, indent=2, sort_keys=True))
            # Add files
            for fi in files_info:
                rel = fi["path"][len("files/"):] if fi["path"].startswith("files/") else fi["path"]
                abs_path = os.path.join(base_dir, rel)
                if os.path.isfile(abs_path):
                    zf.write(abs_path, arcname=fi["path"])  # ensure prefixed with files/
        mem.seek(0)

        filename = f"project-{p.uuid}.zip"
        return send_file(mem, as_attachment=True, download_name=filename, mimetype="application/zip")

    @app.route("/projects/import", methods=["POST"])
    def import_project():
        if 'bundle' not in request.files:
            return jsonify({"error": "No bundle provided. Use multipart/form-data with key 'bundle'"}), 400
        bundle_fs = request.files['bundle']
        if not bundle_fs.filename:
            return jsonify({"error": "Bundle filename is required"}), 400

        # Save to temp to work with zipfile module reliably
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = os.path.join(tmpdir, secure_filename(bundle_fs.filename) or "bundle.zip")
            bundle_fs.save(tmp_path)

            try:
                with zipfile.ZipFile(tmp_path, 'r') as zf:
                    # Read manifest
                    if 'manifest.json' not in zf.namelist():
                        return jsonify({"error": "manifest.json not found in bundle"}), 400
                    manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
                    error = validate_manifest(manifest)
                    if error:
                        return jsonify({"error": f"Invalid manifest: {error}"}), 400

                    metadata = {}
                    if 'metadata.json' in zf.namelist():
                        try:
                            metadata = json.loads(zf.read('metadata.json').decode('utf-8'))
                        except Exception:
                            return jsonify({"error": "Invalid metadata.json"}), 400

                    files_entries = manifest.get('files', [])
                    # Validate file checksums
                    for entry in files_entries:
                        apath = entry.get('path')
                        if not apath or not apath.startswith('files/'):
                            return jsonify({"error": f"Invalid file path in manifest: {apath}"}), 400
                        if apath not in zf.namelist():
                            return jsonify({"error": f"File missing in bundle: {apath}"}), 400
                        data = zf.read(apath)
                        digest = sha256_bytes(data)
                        if digest != entry.get('sha256'):
                            return jsonify({"error": f"Checksum mismatch for {apath}"}), 400

                    proj_info = manifest.get('project', {})
                    # Create new project
                    desired_name = proj_info.get('name') or f"Imported {manifest.get('project', {}).get('id', '')}".strip()
                    name = ensure_unique_project_name(desired_name)
                    description = proj_info.get('description') or ""
                    new_proj = Project(uuid=str(uuidlib.uuid4()), name=name, description=description, metadata=metadata)
                    db.session.add(new_proj)
                    db.session.commit()

                    base_dir = project_files_dir(app, new_proj)
                    ensure_dir(base_dir)

                    # Extract only files from manifest and write safely
                    for entry in files_entries:
                        arcname = entry['path']
                        rel_file_path = arcname[len('files/'):]
                        dest_abs = safe_join(base_dir, rel_file_path)
                        if not dest_abs or not is_subpath(dest_abs, base_dir):
                            db.session.delete(new_proj)
                            db.session.commit()
                            return jsonify({"error": f"Unsafe file path: {rel_file_path}"}), 400
                        ensure_dir(os.path.dirname(dest_abs))
                        with open(dest_abs, 'wb') as f:
                            f.write(zf.read(arcname))

                    return jsonify(project_to_dict(new_proj)), 201

            except zipfile.BadZipFile:
                return jsonify({"error": "Invalid ZIP bundle"}), 400

    def ensure_unique_project_name(desired_name: str) -> str:
        name = desired_name or "Imported Project"
        existing = {p.name for p in Project.query.all()}
        if name not in existing:
            return name
        i = 1
        base = name
        while True:
            candidate = f"{base} ({i})"
            if candidate not in existing:
                return candidate
            i += 1

    def project_files_dir(app_ctx: Flask, project: Project) -> str:
        return os.path.join(app_ctx.config["STORAGE_DIR"], project.uuid, "files")

    def project_to_dict(p: Project) -> Dict:
        return {
            "id": p.id,
            "uuid": p.uuid,
            "name": p.name,
            "description": p.description,
            "metadata": p.metadata or {},
            "created_at": p.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "updated_at": p.updated_at.replace(tzinfo=timezone.utc).isoformat(),
        }

    def build_manifest(project: Project, files_info: List[Dict]) -> Dict:
        return {
            "manifest_version": 1,
            "bundle_type": "project",
            "exported_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
            "app": {"name": APP_NAME, "version": APP_VERSION},
            "project": {
                "id": project.uuid,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "updated_at": project.updated_at.replace(tzinfo=timezone.utc).isoformat(),
                "metadata_schema_version": 1,
            },
            "files": files_info,
        }

    def validate_manifest(m: Dict) -> str | None:
        if not isinstance(m, dict):
            return "Manifest must be a JSON object"
        if m.get("bundle_type") != "project":
            return "bundle_type must be 'project'"
        if int(m.get("manifest_version", 0)) != 1:
            return "Unsupported manifest_version"
        if not isinstance(m.get("project"), dict):
            return "Missing project section"
        if not isinstance(m.get("files"), list):
            return "Missing files list"
        for f in m["files"]:
            if not isinstance(f, dict):
                return "Each file entry must be an object"
            if not f.get("path") or not f["path"].startswith("files/"):
                return "Each file path must start with 'files/'"
            if not f.get("sha256"):
                return "Each file entry must include sha256"
            if "size" not in f:
                return "Each file entry must include size"
        return None

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

