import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import tempfile
import shutil
import json
import traceback
from datetime import datetime
from flask import Flask, request, jsonify

from microdecomp.scanner import scan_project
from microdecomp.git_metrics import get_git_metrics
from microdecomp.heuristics import suggest_decomposition

app = Flask(__name__)

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/analyze", methods=["POST"]) 
def analyze():
    try:
        payload = request.get_json(silent=True) or {}
        path = payload.get("path")
        git_url = payload.get("git_url")
        include_tests = bool(payload.get("include_tests", False))
        thresholds = payload.get("thresholds") or {}
        project_name = payload.get("project_name")

        cleanup_dir = None
        if not path and not git_url and 'file' not in request.files:
            return jsonify({"error": "Provide 'path' or 'git_url' or upload a repository archive as 'file'"}), 400

        if git_url:
            cleanup_dir = tempfile.mkdtemp(prefix="repo_")
            code, out = _git_clone(git_url, cleanup_dir)
            if code != 0:
                if cleanup_dir:
                    shutil.rmtree(cleanup_dir, ignore_errors=True)
                return jsonify({"error": f"Failed to clone git_url: {out}"}), 400
            path = cleanup_dir
        elif 'file' in request.files:
            cleanup_dir = tempfile.mkdtemp(prefix="upload_")
            archive = request.files['file']
            archive_path = os.path.join(cleanup_dir, archive.filename)
            archive.save(archive_path)
            extracted_dir = _extract_archive(archive_path)
            if not extracted_dir:
                shutil.rmtree(cleanup_dir, ignore_errors=True)
                return jsonify({"error": "Unsupported or corrupt archive. Use .zip, .tar.gz, or .tar."}), 400
            path = extracted_dir

        if not project_name:
            project_name = os.path.basename(os.path.abspath(path))

        scan = scan_project(path, include_tests=include_tests)
        git = get_git_metrics(path)
        suggestion = suggest_decomposition(project_name, scan, git, thresholds)
        suggestion["generated_at"] = datetime.utcnow().isoformat() + "Z"

        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

        return app.response_class(
            response=json.dumps(suggestion, ensure_ascii=False, indent=2),
            status=200,
            mimetype="application/json",
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

def _git_clone(git_url: str, dest: str):
    import subprocess
    try:
        res = subprocess.run(["git", "clone", "--depth=1", git_url, dest], capture_output=True, text=True, timeout=300)
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode, out
    except Exception as e:
        return 1, str(e)

def _extract_archive(archive_path: str):
    import tarfile
    import zipfile
    base_dir = os.path.dirname(archive_path)
    extract_to = os.path.join(base_dir, "extracted")
    os.makedirs(extract_to, exist_ok=True)
    try:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_to)
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, 'r:*') as tf:
                tf.extractall(extract_to)
        else:
            return None
        # If single top-level folder, use it
        entries = [e for e in os.listdir(extract_to) if not e.startswith(".")]
        if len(entries) == 1:
            return os.path.join(extract_to, entries[0])
        return extract_to
    except Exception:
        return None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



def create_app():
    return app
