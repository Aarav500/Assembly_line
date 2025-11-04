import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import zipfile
import shutil
import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory

from utils.compare import compare_projects, safe_relpath


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.setdefault("MAX_CONTENT_LENGTH", 100 * 1024 * 1024)  # 100 MB
    app.config.setdefault("UPLOAD_EXTENSIONS", {".zip"})

    # Ensure instance/comparisons directory exists
    comparisons_dir = Path(app.instance_path) / "comparisons"
    comparisons_dir.mkdir(parents=True, exist_ok=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/compare", methods=["POST"]) 
    def compare_upload():
        file_a = request.files.get("project_a")
        file_b = request.files.get("project_b")
        name_a = request.form.get("name_a") or "Project A"
        name_b = request.form.get("name_b") or "Project B"

        if not file_a or not file_b:
            return render_template("index.html", error="Please upload two .zip archives."), 400

        ext_a = Path(file_a.filename or "").suffix.lower()
        ext_b = Path(file_b.filename or "").suffix.lower()
        if ext_a not in app.config["UPLOAD_EXTENSIONS"] or ext_b not in app.config["UPLOAD_EXTENSIONS"]:
            return render_template("index.html", error="Only .zip files are supported."), 400

        session_id = uuid.uuid4().hex
        session_dir = comparisons_dir / session_id
        dir_a = session_dir / "A"
        dir_b = session_dir / "B"
        session_dir.mkdir(parents=True, exist_ok=True)
        dir_a.mkdir(exist_ok=True)
        dir_b.mkdir(exist_ok=True)

        # Save and extract zips
        zip_a_path = session_dir / "a.zip"
        zip_b_path = session_dir / "b.zip"
        file_a.save(str(zip_a_path))
        file_b.save(str(zip_b_path))

        try:
            _extract_zip(zip_a_path, dir_a)
            _extract_zip(zip_b_path, dir_b)
        except zipfile.BadZipFile:
            shutil.rmtree(session_dir, ignore_errors=True)
            return render_template("index.html", error="One of the uploaded files is not a valid ZIP archive."), 400

        # If extracted content has a single top-level directory, use it as root
        dir_a_root = _resolve_root(dir_a)
        dir_b_root = _resolve_root(dir_b)

        # Run comparison
        result = compare_projects(dir_a_root, dir_b_root, label_a=name_a, label_b=name_b)

        # Persist result
        (session_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

        return redirect(url_for("view_compare", session_id=session_id))

    @app.route("/compare/<session_id>")
    def view_compare(session_id):
        session_dir = Path(app.instance_path) / "comparisons" / session_id
        if not session_dir.exists():
            abort(404)
        result_path = session_dir / "result.json"
        if not result_path.exists():
            abort(404)
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return render_template("compare.html", data=data, session_id=session_id)

    @app.route("/compare/<session_id>/diff")
    def diff_file(session_id):
        from utils.compare import generate_html_diff, is_text_file

        relpath = request.args.get("path")
        if not relpath:
            abort(400)
        session_dir = Path(app.instance_path) / "comparisons" / session_id
        if not session_dir.exists():
            abort(404)

        dir_a = _resolve_root(session_dir / "A")
        dir_b = _resolve_root(session_dir / "B")

        # Sanitize path
        relpath = safe_relpath(relpath)
        path_a = dir_a / relpath
        path_b = dir_b / relpath

        exists_a = path_a.exists()
        exists_b = path_b.exists()

        label_a = "A"
        label_b = "B"
        # Read labels from result.json if present
        result_path = session_dir / "result.json"
        if result_path.exists():
            try:
                d = json.loads(result_path.read_text(encoding="utf-8"))
                label_a = d.get("labels", {}).get("a", label_a)
                label_b = d.get("labels", {}).get("b", label_b)
            except Exception:
                pass

        if exists_a and exists_b:
            # Both exist
            if is_text_file(path_a) and is_text_file(path_b):
                html = generate_html_diff(path_a, path_b, label_a=label_a, label_b=label_b)
                return html
            else:
                return _binary_diff_message(label_a, label_b)
        elif exists_a:
            if is_text_file(path_a):
                html = generate_html_diff(path_a, None, label_a=label_a, label_b=f"{label_b} (missing)")
                return html
            else:
                return _binary_diff_message(label_a, f"{label_b} (missing)")
        elif exists_b:
            if is_text_file(path_b):
                html = generate_html_diff(None, path_b, label_a=f"{label_a} (missing)", label_b=label_b)
                return html
            else:
                return _binary_diff_message(f"{label_a} (missing)", label_b)
        else:
            abort(404)

    @app.route("/static/<path:filename>")
    def static_files(filename):
        # Serve static files when running without a web server
        static_dir = Path(app.root_path) / "static"
        return send_from_directory(str(static_dir), filename)

    return app


def _binary_diff_message(label_a, label_b):
    return (
        f"<div class='binary-diff'>Cannot display textual diff. One or both files are binary or not decodable.<br>"
        f"Comparing: <strong>{label_a}</strong> vs <strong>{label_b}</strong></div>"
    )


def _extract_zip(zip_path: Path, target_dir: Path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        _safe_extractall(zf, target_dir)


def _safe_extractall(zf: zipfile.ZipFile, target_dir: Path):
    for member in zf.infolist():
        member_path = Path(member.filename)
        # Skip absolute or parent-traversal entries
        if member_path.is_absolute() or any(part == ".." for part in member_path.parts):
            continue
        dest_path = (target_dir / member_path).resolve()
        if not str(dest_path).startswith(str(target_dir.resolve())):
            continue
        if member.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, 'r') as src, open(dest_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)


def _resolve_root(base_dir: Path) -> Path:
    # If the directory has exactly one child directory and no files, dive into it.
    try:
        entries = [p for p in base_dir.iterdir() if not p.name.startswith("__MACOSX")]
    except FileNotFoundError:
        return base_dir
    if len(entries) == 1 and entries[0].is_dir():
        # Only if there are no files at the top level
        if not any(p.is_file() for p in base_dir.iterdir()):
            return entries[0]
    return base_dir


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

