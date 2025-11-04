import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sys
from flask import Flask, render_template, request, jsonify
from git_utils import (
    GitError,
    get_current_branch,
    get_remotes,
    create_branch,
    push_current_branch,
    parse_remote_url,
)
from pr_providers import get_pr_provider

app = Flask(__name__)

REPO_PATH = os.environ.get("GIT_UI_REPO_PATH", os.getcwd())
DEFAULT_REMOTE = os.environ.get("GIT_UI_REMOTE", "origin")
DEFAULT_BASE_BRANCH = os.environ.get("GIT_UI_BASE_BRANCH", "main")


def ensure_repo() -> None:
    if not os.path.isdir(REPO_PATH):
        raise RuntimeError(f"Repo path does not exist: {REPO_PATH}")
    # Quick check if .git exists
    if not os.path.isdir(os.path.join(REPO_PATH, ".git")):
        raise RuntimeError(f"Path is not a git repository: {REPO_PATH}")


@app.route("/")
def index():
    try:
        ensure_repo()
        branch = get_current_branch(REPO_PATH)
        remotes = get_remotes(REPO_PATH)
        origin_url = remotes.get(DEFAULT_REMOTE, {}).get("push")
        parsed = parse_remote_url(origin_url) if origin_url else None
        repo_display = f"{parsed['owner']}/{parsed['repo']}" if parsed else "Unknown"
        return render_template(
            "index.html",
            repo_path=REPO_PATH,
            branch=branch,
            remotes=remotes,
            origin_url=origin_url,
            repo_display=repo_display,
            default_base=DEFAULT_BASE_BRANCH,
        )
    except Exception as e:
        return render_template("index.html", error=str(e), repo_path=REPO_PATH)


@app.route("/api/status")
def api_status():
    try:
        ensure_repo()
        branch = get_current_branch(REPO_PATH)
        remotes = get_remotes(REPO_PATH)
        origin_url = remotes.get(DEFAULT_REMOTE, {}).get("push")
        parsed = parse_remote_url(origin_url) if origin_url else None
        return jsonify({
            "ok": True,
            "repo_path": REPO_PATH,
            "branch": branch,
            "remotes": remotes,
            "origin": parsed,
            "origin_url": origin_url,
        })
    except GitError as ge:
        return jsonify({"ok": False, "error": ge.to_dict()}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/create-branch", methods=["POST"])
def api_create_branch():
    try:
        ensure_repo()
        data = request.get_json(force=True) or {}
        name = data.get("branch")
        base = data.get("base")
        push = bool(data.get("push"))
        if not name:
            return jsonify({"ok": False, "error": "Missing 'branch' name"}), 400
        result = create_branch(REPO_PATH, name, base)
        pushed = None
        if push:
            pushed = push_current_branch(REPO_PATH, DEFAULT_REMOTE)
        return jsonify({
            "ok": True,
            "created": result,
            "pushed": pushed,
            "branch": get_current_branch(REPO_PATH),
        })
    except GitError as ge:
        return jsonify({"ok": False, "error": ge.to_dict()}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/push", methods=["POST"])
def api_push():
    try:
        ensure_repo()
        pushed = push_current_branch(REPO_PATH, DEFAULT_REMOTE)
        return jsonify({"ok": True, "pushed": pushed})
    except GitError as ge:
        return jsonify({"ok": False, "error": ge.to_dict()}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/create-pr", methods=["POST"])
def api_create_pr():
    try:
        ensure_repo()
        data = request.get_json(force=True) or {}
        title = data.get("title")
        body = data.get("body")
        base = data.get("base") or DEFAULT_BASE_BRANCH
        head = data.get("head") or get_current_branch(REPO_PATH)
        draft = bool(data.get("draft", False))
        token = data.get("token") or os.environ.get("GITHUB_TOKEN")
        if not token:
            return jsonify({"ok": False, "error": "Missing 'token' and GITHUB_TOKEN not set"}), 400

        remotes = get_remotes(REPO_PATH)
        origin_url = remotes.get(DEFAULT_REMOTE, {}).get("push")
        if not origin_url:
            return jsonify({"ok": False, "error": f"Remote '{DEFAULT_REMOTE}' not found"}), 400

        remote = parse_remote_url(origin_url)
        provider = get_pr_provider(remote["host"], token)

        if not title:
            title = f"PR: {head} -> {base}"

        pr = provider.create_pr(
            owner=remote["owner"],
            repo=remote["repo"],
            title=title,
            body=body or "",
            head=head,
            base=base,
            draft=draft,
        )
        return jsonify({"ok": True, "pr": pr})
    except GitError as ge:
        return jsonify({"ok": False, "error": ge.to_dict()}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/healthz")
def healthz():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app
