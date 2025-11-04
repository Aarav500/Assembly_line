import json
import os
import shutil
import tempfile
import uuid
from typing import List

from flask import Blueprint, current_app, jsonify, request

from app.services.conftest_runner import run_conftest, ConftestNotFoundError
from app.utils.archive import save_uploads_to_temp, collect_candidate_files

bp = Blueprint("routes", __name__)


@bp.route("/health", methods=["GET"])  # Simple health check
def health():
    return jsonify({"status": "ok"})


@bp.route("/api/policies", methods=["GET"])  # List policy files
def list_policies():
    policy_dir = request.args.get("policy_dir") or current_app.config["POLICY_DIR"]
    files_info = []
    if os.path.isdir(policy_dir):
        for root, _, files in os.walk(policy_dir):
            for f in files:
                if f.endswith(".rego"):
                    path = os.path.join(root, f)
                    rel = os.path.relpath(path, policy_dir)
                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            head = fh.readline().strip()
                    except Exception:
                        head = ""
                    files_info.append({"path": rel, "first_line": head})
    return jsonify({"policy_dir": policy_dir, "policies": files_info})


@bp.route("/api/scan", methods=["POST"])  # Scan uploaded IaC/manifests with conftest
def scan():
    # Determine policy directory and flags
    policy_dir = request.args.get("policy_dir") or request.form.get("policy_dir") or current_app.config["POLICY_DIR"]
    fail_on_warn_param = request.args.get("fail_on_warn") or request.form.get("fail_on_warn")
    if fail_on_warn_param is None:
        fail_on_warn = bool(current_app.config.get("FAIL_ON_WARN", False))
    else:
        fail_on_warn = str(fail_on_warn_param).lower() in ("1", "true", "yes")

    # Create a scratch workspace for this request
    base_tmp = current_app.config.get("TEMP_BASE_DIR")
    os.makedirs(base_tmp, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix=f"scan-{uuid.uuid4()}-", dir=base_tmp)

    try:
        # Expect multipart/form-data with one or more files (field name: file or files)
        if not request.content_type or not request.content_type.startswith("multipart/"):
            return jsonify({
                "status": "error",
                "error": "Unsupported Content-Type. Use multipart/form-data with 'file' or 'files' fields.",
            }), 400

        uploads: List = []
        if "files" in request.files:
            uploads = request.files.getlist("files")
        elif "file" in request.files:
            uploads = [request.files["file"]]

        if not uploads:
            return jsonify({"status": "error", "error": "No file(s) uploaded."}), 400

        saved_roots = save_uploads_to_temp(uploads, workdir)

        # Collect candidate files beneath saved roots
        include_exts = set(current_app.config["ALLOWED_EXTENSIONS"]) if current_app.config.get("ALLOWED_EXTENSIONS") else None
        targets: List[str] = []
        for root in saved_roots:
            files = collect_candidate_files(root, include_exts)
            targets.extend(files)

        if not targets:
            return jsonify({
                "status": "error",
                "error": "No supported files found to scan.",
                "supported_extensions": sorted(list(include_exts or [])),
            }), 400

        try:
            result = run_conftest(
                paths=targets,
                policy_dir=policy_dir,
                fail_on_warn=fail_on_warn,
                conftest_bin=current_app.config.get("CONFTEST_BIN", "conftest"),
            )
        except ConftestNotFoundError as e:
            return jsonify({"status": "error", "error": str(e)}), 500

        return jsonify(result), (400 if result.get("summary", {}).get("exit_code", 1) != 0 else 200)

    finally:
        # Cleanup workspace
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass

