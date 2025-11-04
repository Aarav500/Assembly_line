import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import shutil
import tempfile
import uuid
import datetime
import subprocess
from flask import Flask, request, jsonify

from config import (
    DATA_DIR,
    SCANS_DIR,
    WORK_DIR,
    MAX_ARCHIVE_SIZE_BYTES,
    MAX_FILE_SIZE_BYTES,
    MAX_FILES_TO_SCAN,
    ALLOWED_IMPORT_METHODS,
)
from utils import ensure_dirs, safe_extract_zip, generate_scan_id, is_zipfile_safe
from secret_scanner import scan_directory

app = Flask(__name__)

ensure_dirs([DATA_DIR, SCANS_DIR, WORK_DIR])


def save_scan_result(scan_id: str, result: dict):
    out_path = os.path.join(SCANS_DIR, f"{scan_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def load_scan_result(scan_id: str):
    in_path = os.path.join(SCANS_DIR, f"{scan_id}.json")
    if not os.path.exists(in_path):
        return None
    with open(in_path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/scans")
def list_scans():
    scans = []
    for name in os.listdir(SCANS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(SCANS_DIR, name), "r", encoding="utf-8") as f:
                data = json.load(f)
                # Provide a lightweight summary list
                scans.append({
                    "id": data.get("id"),
                    "source": data.get("source"),
                    "created_at": data.get("created_at"),
                    "summary": data.get("summary", {}),
                    "truncated": data.get("truncated", False),
                    "warnings": data.get("warnings", [])
                })
        except Exception:
            continue
    scans.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify({"scans": scans})


@app.get("/scan/<scan_id>")
def get_scan(scan_id):
    data = load_scan_result(scan_id)
    if not data:
        return jsonify({"error": "not_found"}), 404
    return jsonify(data)


@app.post("/import")
def import_project():
    """
    Import a project via:
    - JSON body: {"git_url": "https://..."}
    - multipart/form-data with file field name 'archive' (zip)
    Then run secret scanner against imported contents.
    """
    warnings = []
    now = datetime.datetime.utcnow().isoformat() + "Z"
    scan_id = generate_scan_id()
    work_dir = os.path.join(WORK_DIR, f"import_{scan_id}")
    os.makedirs(work_dir, exist_ok=True)

    git_url = None
    upload_filename = None

    try:
        if request.is_json:
            body = request.get_json(silent=True) or {}
            git_url = body.get("git_url")
            if git_url and "git" not in ALLOWED_IMPORT_METHODS:
                return jsonify({"error": "git_import_disabled"}), 400
        elif request.content_type and request.content_type.startswith("multipart/form-data"):
            if "archive" not in request.files:
                return jsonify({"error": "missing_archive"}), 400
            if "zip" not in ALLOWED_IMPORT_METHODS:
                return jsonify({"error": "zip_import_disabled"}), 400

            archive = request.files["archive"]
            upload_filename = archive.filename or "upload.zip"

            # Save to temp file and enforce size limit
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
            os.close(tmp_fd)
            size = 0
            with open(tmp_path, "wb") as out:
                chunk = archive.stream.read(8192)
                while chunk:
                    size += len(chunk)
                    if size > MAX_ARCHIVE_SIZE_BYTES:
                        out.close()
                        os.remove(tmp_path)
                        return jsonify({"error": "archive_too_large", "max_bytes": MAX_ARCHIVE_SIZE_BYTES}), 413
                    out.write(chunk)
                    chunk = archive.stream.read(8192)

            # Basic validation and extraction
            is_ok, reason = is_zipfile_safe(tmp_path)
            if not is_ok:
                os.remove(tmp_path)
                return jsonify({"error": "invalid_zip", "reason": reason}), 400

            try:
                safe_extract_zip(tmp_path, work_dir)
            finally:
                os.remove(tmp_path)
        else:
            return jsonify({"error": "unsupported_content_type"}), 415

        source = None
        if git_url:
            source = {"type": "git", "git_url": git_url}
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            # Simple scheme allow-list
            if not (git_url.startswith("https://") or git_url.startswith("ssh://") or git_url.startswith("git@")):
                return jsonify({"error": "unsupported_git_scheme"}), 400
            try:
                subprocess.run(
                    ["git", "clone", "--depth=1", "--no-tags", git_url, work_dir],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=180,
                    env=env,
                )
            except subprocess.CalledProcessError as e:
                return jsonify({"error": "git_clone_failed", "stderr": e.stderr.decode("utf-8", errors="ignore")}), 400
            except subprocess.TimeoutExpired:
                return jsonify({"error": "git_clone_timeout"}), 408
        else:
            source = {"type": "zip", "filename": upload_filename}

        # Run scanner
        scan_result = scan_directory(
            root_path=work_dir,
            max_file_size=MAX_FILE_SIZE_BYTES,
            max_files=MAX_FILES_TO_SCAN,
        )

        result_doc = {
            "id": scan_id,
            "source": source,
            "created_at": now,
            "summary": scan_result.get("summary", {}),
            "findings": scan_result.get("findings", []),
            "truncated": scan_result.get("truncated", False),
            "warnings": warnings + scan_result.get("warnings", []),
            "engine": scan_result.get("engine", {}),
        }

        save_scan_result(scan_id, result_doc)
        return jsonify(result_doc), 201

    finally:
        # Cleanup working dir to avoid storing code, retain only results
        try:
            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)



def create_app():
    return app
