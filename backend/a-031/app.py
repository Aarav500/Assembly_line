import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import base64
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from github_client import GitHubClient
from suggestion_engine import suggest_one_line_fixes

load_dotenv()

app = Flask(__name__)


def get_token_from_request(req):
    token = os.getenv("GITHUB_TOKEN")
    auth = req.headers.get("Authorization", "").strip()
    if not token and auth.lower().startswith("token "):
        token = auth.split(" ", 1)[1]
    if not token and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
    return token


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})


@app.route("/suggest", methods=["POST"])
def suggest():
    payload = request.get_json(silent=True) or {}
    suggestions = suggest_one_line_fixes(payload)
    return jsonify({"suggestions": suggestions})


@app.route("/create_pr", methods=["POST"])
def create_pr():
    payload = request.get_json(silent=True) or {}

    # Required repo info
    owner = payload.get("repo_owner")
    repo = payload.get("repo_name")
    base_branch = payload.get("base_branch", "main")
    file_path = payload.get("target_file_path")

    if not owner or not repo or not file_path:
        return jsonify({
            "error": "repo_owner, repo_name, and target_file_path are required"
        }), 400

    token = get_token_from_request(request)
    if not token:
        return jsonify({"error": "GitHub token not provided"}), 401

    gh = GitHubClient(token)

    branch_name = payload.get("branch_name") or f"fix/{uuid.uuid4().hex[:8]}"

    # Fetch file content from base branch (if exists)
    file_content_text = ""
    file_sha = None
    file_exists = True
    get_file_ok = True
    try:
        content, sha = gh.get_file(owner, repo, file_path, base_branch)
        file_content_text = content
        file_sha = sha
    except Exception as e:
        # If file not found, allow creating a new file
        message = str(e)
        if "404" in message or "not found" in message.lower():
            file_exists = False
            file_content_text = ""
            file_sha = None
        else:
            get_file_ok = False

    if not get_file_ok:
        return jsonify({"error": "Failed to fetch file from base branch"}), 400

    # Compute new content either via direct content or search/replace
    new_content = payload.get("new_content")
    search = payload.get("search")
    replace = payload.get("replace")

    if new_content is None:
        if not search or replace is None:
            return jsonify({
                "error": "Provide either new_content or both search and replace"
            }), 400
        if search not in file_content_text:
            return jsonify({
                "error": "Search string not found in file on base branch"
            }), 400
        new_content = file_content_text.replace(search, replace, 1)

    # Create branch from base
    try:
        gh.create_branch(owner, repo, branch_name, base_branch)
    except Exception as e:
        return jsonify({"error": f"Failed to create branch: {e}"}), 400

    # Update (or create) file on new branch
    commit_message = payload.get("commit_message") or f"Apply one-line fix to {file_path}"
    try:
        gh.update_file(owner, repo, file_path, new_content, commit_message, branch_name, sha=file_sha if file_exists else None)
    except Exception as e:
        return jsonify({"error": f"Failed to update file: {e}"}), 400

    # Create PR
    pr_title = payload.get("pr_title") or commit_message
    pr_body = payload.get("pr_body") or "Automated minimal viable one-line fix."
    try:
        pr = gh.create_pr(owner, repo, pr_title, pr_body, head_branch=branch_name, base_branch=payload.get("base_branch", "main"))
    except Exception as e:
        return jsonify({"error": f"Failed to create PR: {e}"}), 400

    return jsonify({
        "branch": branch_name,
        "commit_message": commit_message,
        "pull_request": pr
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=bool(os.getenv("DEBUG", "").lower() in ["1", "true", "yes"]))



def create_app():
    return app
