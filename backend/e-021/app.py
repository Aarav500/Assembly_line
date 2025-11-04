import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
from flask import Flask, request, jsonify
from datetime import datetime

from config import Config
from drift.detector import detect_drift, load_desired_state
from drift.suggester import build_remediation_suggestions
from storage import DriftStorage
from utils.git import GitOps
from utils.github import GitHubPR

app = Flask(__name__)
config = Config()
storage = DriftStorage(config)

def _json_error(message, status=400, details=None):
    payload = {"error": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status

@app.route("/health", methods=["GET"])  
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})

@app.route("/api/drift/run", methods=["POST"])  
def run_drift_detection():
    try:
        body = request.get_json(silent=True) or {}
        desired_path = body.get("desired_state_path") or config.DESIRED_STATE_PATH
        provider = body.get("provider", "file")  # file | inline | terraform_show
        provider_opts = body.get("provider_options", {})
        inline_actual_state = body.get("actual_state")

        desired = load_desired_state(desired_path)
        report = detect_drift(
            desired_state=desired,
            provider=provider,
            provider_options=provider_opts,
            inline_actual_state=inline_actual_state,
        )
        saved = storage.save_report(report)
        return jsonify({"ok": True, "report": saved}), 200
    except Exception as e:
        return _json_error("Failed to run drift detection", 500, str(e))

@app.route("/api/drift/reports", methods=["GET"])  
def list_reports():
    try:
        reports = storage.list_reports()
        return jsonify({"reports": reports})
    except Exception as e:
        return _json_error("Failed to list reports", 500, str(e))

@app.route("/api/drift/reports/<rid>", methods=["GET"])  
def get_report(rid):
    try:
        report = storage.load_report(rid)
        if not report:
            return _json_error("Report not found", 404)
        return jsonify(report)
    except Exception as e:
        return _json_error("Failed to load report", 500, str(e))

@app.route("/api/remediation/suggest", methods=["POST"])  
def remediation_suggest():
    try:
        body = request.get_json(silent=True) or {}
        rid = body.get("report_id")
        report = body.get("report")
        strategy = body.get("strategy", "code_to_actual")  # code_to_actual | actual_to_code
        desired_path = body.get("desired_state_path") or config.DESIRED_STATE_PATH

        if not report and rid:
            report = storage.load_report(rid)
            if not report:
                return _json_error("Report not found", 404)

        if not report:
            return _json_error("report or report_id required", 400)

        suggestions = build_remediation_suggestions(report, desired_path, strategy)
        return jsonify({"ok": True, "suggestions": suggestions})
    except Exception as e:
        return _json_error("Failed to build remediation suggestions", 500, str(e))

@app.route("/api/remediation/auto-pr", methods=["POST"])  
def remediation_auto_pr():
    try:
        body = request.get_json(silent=True) or {}
        suggestions = body.get("suggestions")
        branch_name = body.get("branch_name") or f"drift/remediate-{uuid.uuid4().hex[:8]}"
        pr_title = body.get("pr_title") or "Infrastructure drift remediation"
        pr_body = body.get("pr_body") or "Automated remediation suggestions applied."
        base_branch = body.get("base_branch") or os.getenv("BASE_BRANCH", "main")
        dry_run = bool(body.get("dry_run", False))

        if not suggestions:
            return _json_error("suggestions required", 400)

        git_ops = GitOps()
        applied_files = []
        diffs = []

        if not dry_run:
            git_ops.ensure_repo()
            git_ops.create_branch(branch_name)

        for fp in suggestions.get("file_patches", []):
            path = fp["path"]
            after = fp.get("after", "")
            if not dry_run:
                git_ops.apply_file_change(path, after)
            applied_files.append(path)
            diffs.append({"path": path, "diff": fp.get("diff")})

        if not dry_run:
            if applied_files:
                git_ops.commit_all(pr_title)
                push_result = git_ops.push_branch(branch_name)
            else:
                push_result = {"pushed": False, "reason": "No files to change"}
        else:
            push_result = {"pushed": False, "reason": "dry_run"}

        pr_info = {
            "created": False,
            "url": None,
            "preview": None,
        }

        if not dry_run and applied_files:
            gh_repo = os.getenv("GITHUB_REPOSITORY")  # owner/repo
            gh_token = os.getenv("GITHUB_TOKEN")
            if gh_repo and gh_token:
                gh = GitHubPR(gh_repo, gh_token)
                pr = gh.create_pr(title=pr_title, head=branch_name, base=base_branch, body=pr_body)
                pr_info.update({"created": True, "url": pr.get("html_url"), "number": pr.get("number")})
            else:
                pr_info["preview"] = {
                    "title": pr_title,
                    "body": pr_body,
                    "head": branch_name,
                    "base": base_branch,
                }

        return jsonify({
            "ok": True,
            "branch": branch_name,
            "applied_files": applied_files,
            "diffs": diffs,
            "push": push_result,
            "pr": pr_info,
        })
    except Exception as e:
        return _json_error("Failed to create auto PR", 500, str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))



def create_app():
    return app


@app.route('/infrastructure/register', methods=['POST'])
def _auto_stub_infrastructure_register():
    return 'Auto-generated stub for /infrastructure/register', 200


@app.route('/infrastructure/check-drift', methods=['POST'])
def _auto_stub_infrastructure_check_drift():
    return 'Auto-generated stub for /infrastructure/check-drift', 200


@app.route('/infrastructure/remediation-pr', methods=['POST'])
def _auto_stub_infrastructure_remediation_pr():
    return 'Auto-generated stub for /infrastructure/remediation-pr', 200
