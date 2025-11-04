import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from secret_scanner import SecretScanner
from remediation import apply_redactions
from github_client import GitClient

app = Flask(__name__)

SCANNER = SecretScanner()
GIT_CLIENT = GitClient()

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/scan")
def scan_endpoint():
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("path", ".")
    include_globs = data.get("include_globs")
    exclude_globs = data.get("exclude_globs")
    staged = bool(data.get("staged", False))

    if not os.path.isdir(path):
        return jsonify({"error": f"Path not found: {path}"}), 400

    findings, stats = SCANNER.scan_path(path, include_globs=include_globs, exclude_globs=exclude_globs, staged=staged)
    return jsonify({
        "findings": findings,
        "summary": {
            "files_scanned": stats.get("files_scanned", 0),
            "findings": len(findings)
        }
    })

@app.post("/remediate")
def remediate_endpoint():
    data = request.get_json(force=True, silent=True) or {}

    path = data.get("path", ".")
    if not os.path.isdir(path):
        return jsonify({"error": f"Path not found: {path}"}), 400

    include_globs = data.get("include_globs")
    exclude_globs = data.get("exclude_globs")
    staged = bool(data.get("staged", False))
    placeholder = data.get("placeholder", "<REDACTED>")

    branch_name = data.get("branch_name", "chore/secret-redaction")
    base_branch = data.get("base_branch", "main")
    commit_message = data.get("commit_message", "chore: redact detected secrets")
    pr_title = data.get("pr_title", "Redact detected secrets")
    pr_body = data.get("pr_body", "Automated remediation: redacted detected secrets.")

    gh = data.get("github", {})
    owner = gh.get("owner")
    repo_name = gh.get("repo")
    remote_name = gh.get("remote", "origin")

    dry_run = bool(data.get("dry_run", False))

    findings, stats = SCANNER.scan_path(path, include_globs=include_globs, exclude_globs=exclude_globs, staged=staged)
    if not findings:
        return jsonify({
            "message": "No secrets detected.",
            "summary": {"files_scanned": stats.get("files_scanned", 0), "findings": 0}
        })

    if dry_run:
        return jsonify({
            "message": "Dry-run: remediation changes not applied.",
            "findings": findings,
            "summary": {"files_scanned": stats.get("files_scanned", 0), "findings": len(findings)}
        })

    try:
        changed_files, changes = apply_redactions(findings, base_path=path, placeholder=placeholder)
    except Exception as e:
        return jsonify({"error": f"Failed to apply redactions: {e}"}), 500

    if not changed_files:
        return jsonify({"message": "No applicable redactions were made.", "findings": findings})

    # Commit, push, PR
    try:
        repo = GIT_CLIENT.ensure_repo(path)
        GIT_CLIENT.checkout_base(repo, base_branch)
        GIT_CLIENT.create_or_reset_branch(repo, branch_name, base_branch)
        GIT_CLIENT.add_and_commit(repo, changed_files, commit_message)
        GIT_CLIENT.push_branch(repo, branch_name, remote_name)

        pr_url = None
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if owner and repo_name and token:
            pr_url = GIT_CLIENT.create_github_pr(owner=owner, repo=repo_name, head=branch_name, base=base_branch, title=pr_title, body=pr_body, token=token)

        return jsonify({
            "message": "Redactions applied and committed.",
            "changed_files": changed_files,
            "changes": changes,
            "pull_request_url": pr_url
        })
    except Exception as e:
        return jsonify({"error": f"Git/PR operation failed: {e}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app
