import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sys
from pathlib import Path
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import shutil
import traceback

from config import (
    PROJECTS_ROOT,
    TEMP_UPLOADS,
    MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS,
    ALLOWED_BASE_DIRS,
    USE_SYMLINKS,
)
from utils import (
    ensure_dir,
    safe_extract_zip,
    sanitize_project_name,
    unique_project_path,
    is_source_dir_allowed,
    link_or_copy_project,
    get_project_metadata,
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # Ensure data directories
    ensure_dir(PROJECTS_ROOT)
    ensure_dir(TEMP_UPLOADS)

    @app.route("/")
    def index():
        projects = []
        try:
            for p in sorted(Path(PROJECTS_ROOT).iterdir()):
                if p.is_dir():
                    meta = get_project_metadata(p)
                    projects.append({
                        "name": p.name,
                        "path": str(p),
                        "files": meta.get("files", 0),
                        "size_bytes": meta.get("size_bytes", 0),
                        "link": meta.get("link", False),
                    })
        except FileNotFoundError:
            pass
        return render_template("index.html", projects=projects, allowed_bases=ALLOWED_BASE_DIRS, use_symlinks=USE_SYMLINKS)

    @app.route("/projects", methods=["GET"])
    def list_projects():
        data = []
        for p in sorted(Path(PROJECTS_ROOT).iterdir()):
            if p.is_dir():
                meta = get_project_metadata(p)
                data.append({
                    "name": p.name,
                    "path": str(p),
                    "files": meta.get("files", 0),
                    "size_bytes": meta.get("size_bytes", 0),
                    "link": meta.get("link", False),
                })
        return jsonify({"projects": data})

    @app.route("/add_project", methods=["POST"])
    def add_project():
        # Handles both upload and path based addition from the same form
        try:
            mode = request.form.get("mode")  # 'upload' or 'path'
            project_name = sanitize_project_name(request.form.get("project_name", "").strip())

            if mode == "upload":
                file = request.files.get("project_zip")
                if not file or file.filename == "":
                    flash("No file provided", "error")
                    return redirect(url_for("index"))

                filename = secure_filename(file.filename)
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                if ext not in ALLOWED_EXTENSIONS:
                    flash(f"Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed.", "error")
                    return redirect(url_for("index"))

                # If project_name not given, derive from zip base name
                zip_basename = Path(filename).stem
                if not project_name:
                    project_name = sanitize_project_name(zip_basename)
                if not project_name:
                    flash("Invalid project name.", "error")
                    return redirect(url_for("index"))

                tmp_zip_path = Path(TEMP_UPLOADS) / filename
                file.save(tmp_zip_path)

                dest_path = unique_project_path(PROJECTS_ROOT, project_name)
                ensure_dir(dest_path)

                try:
                    safe_extract_zip(tmp_zip_path, dest_path)
                except Exception as e:
                    # Clean up partially extracted dir
                    try:
                        shutil.rmtree(dest_path, ignore_errors=True)
                    finally:
                        pass
                    flash(f"Failed to extract zip: {e}", "error")
                    return redirect(url_for("index"))
                finally:
                    try:
                        tmp_zip_path.unlink(missing_ok=True)
                    except Exception:
                        pass

                flash(f"Project '{dest_path.name}' added from upload.", "success")
                return redirect(url_for("index"))

            elif mode == "path":
                source_path_raw = request.form.get("source_path", "").strip()
                operation = request.form.get("operation", "link")  # 'link' or 'copy'

                if not source_path_raw:
                    flash("Source path is required.", "error")
                    return redirect(url_for("index"))

                source_path = Path(source_path_raw)

                if not source_path.exists() or not source_path.is_dir():
                    flash("Provided source path does not exist or is not a directory.", "error")
                    return redirect(url_for("index"))

                if not is_source_dir_allowed(source_path):
                    flash("Source path is not within allowed base directories.", "error")
                    return redirect(url_for("index"))

                if not project_name:
                    project_name = sanitize_project_name(source_path.name)
                if not project_name:
                    flash("Invalid project name.", "error")
                    return redirect(url_for("index"))

                dest_path = unique_project_path(PROJECTS_ROOT, project_name)

                try:
                    link = (operation == "link")
                    result = link_or_copy_project(source_path, dest_path, prefer_symlink=(link and USE_SYMLINKS))
                except Exception as e:
                    flash(f"Failed to add project from path: {e}", "error")
                    return redirect(url_for("index"))

                mode_str = "linked" if result.get("linked") else "copied"
                flash(f"Project '{dest_path.name}' {mode_str} from {source_path}", "success")
                return redirect(url_for("index"))

            else:
                flash("Invalid mode.", "error")
                return redirect(url_for("index"))
        except Exception as e:
            traceback.print_exc()
            flash(f"Unexpected error: {e}", "error")
            return redirect(url_for("index"))

    @app.route("/api/projects", methods=["POST"])
    def api_add_project():
        # JSON API for automation
        try:
            payload = request.get_json(force=True)
            mode = payload.get("mode")
            project_name = sanitize_project_name(payload.get("project_name", ""))

            if mode == "path":
                source_path_raw = payload.get("source_path", "")
                operation = payload.get("operation", "link")
                if not source_path_raw:
                    return jsonify({"error": "source_path is required"}), 400
                source_path = Path(source_path_raw)
                if not source_path.exists() or not source_path.is_dir():
                    return jsonify({"error": "source path does not exist or is not a directory"}), 400
                if not is_source_dir_allowed(source_path):
                    return jsonify({"error": "source path not allowed"}), 403
                if not project_name:
                    project_name = sanitize_project_name(source_path.name)
                dest_path = unique_project_path(PROJECTS_ROOT, project_name)
                result = link_or_copy_project(source_path, dest_path, prefer_symlink=(operation == "link" and USE_SYMLINKS))
                meta = get_project_metadata(dest_path)
                return jsonify({
                    "name": dest_path.name,
                    "path": str(dest_path),
                    "linked": result.get("linked", False),
                    "files": meta.get("files", 0),
                    "size_bytes": meta.get("size_bytes", 0),
                }), 201
            else:
                return jsonify({"error": "Invalid mode"}), 400
        except Exception as e:
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
