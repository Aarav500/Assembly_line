import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hmac
import hashlib
import json
import os
from flask import Flask, request, jsonify

from config import Config
from github_client import GitHubClient
from risk import analyze_pr_changes, build_risk_comment, overall_risk_level

app = Flask(__name__)
config = Config()

gh = GitHubClient(
    token=config.github_token,
    app_id=config.github_app_id,
    private_key_pem=config.github_app_private_key,
)

SAFE_ACTIONS = {"opened", "synchronize", "edited", "reopened", "ready_for_review"}
BOT_LOGINS = {"dependabot[bot]", "renovate[bot]"}
COMMENT_MARKER = "<!-- risk-comment:v1 -->"


def verify_signature(req):
    secret = config.github_webhook_secret
    if not secret:
        # If no secret configured, skip verification (not recommended for production)
        return True
    signature_header = req.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        return False
    signature = signature_header.split("=", 1)[1]
    mac = hmac.new(secret.encode("utf-8"), msg=req.data, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    return hmac.compare_digest(expected, signature)


@app.route("/healthz", methods=["GET"])\
@app.route("/", methods=["GET"])  # simple root health
def health():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"]) 
def webhook():
    if not verify_signature(request):
        return jsonify({"error": "invalid signature"}), 401

    event = request.headers.get("X-GitHub-Event")
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    if event == "ping":
        return jsonify({"msg": "pong"})

    if event != "pull_request":
        return jsonify({"msg": f"ignored event {event}"})

    action = payload.get("action")
    if action not in SAFE_ACTIONS:
        return jsonify({"msg": f"ignored action {action}"})

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    owner_login = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")
    if not owner_login or not repo_name:
        return jsonify({"error": "missing repo info"}), 400

    pr_number = pr.get("number")
    pr_user_login = (pr.get("user") or {}).get("login", "")
    sender_login = (payload.get("sender") or {}).get("login", "")

    # Only handle Dependabot/Renovate PRs or branches named accordingly
    is_bot = pr_user_login in BOT_LOGINS or sender_login in BOT_LOGINS
    head_ref = (pr.get("head") or {}).get("ref", "")
    if not is_bot and not head_ref.startswith("dependabot/") and not head_ref.startswith("renovate/"):
        return jsonify({"msg": "ignored non-bot PR"})

    # Skip draft PRs optionally
    if pr.get("draft") and not config.include_drafts:
        return jsonify({"msg": "ignored draft PR"})

    # Determine installation id for GitHub App auth if available
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    gh.set_installation(installation_id)

    # Fetch changed files and patches
    try:
        files = gh.list_pull_files(owner_login, repo_name, pr_number)
    except Exception as e:
        return jsonify({"error": f"failed to list files: {e}"}), 500

    title = pr.get("title") or ""
    body = pr.get("body") or ""

    changes = analyze_pr_changes(files, title=title, body=body)

    # If no dependency changes detected, do nothing
    if not changes.get("dependencies"):
        return jsonify({"msg": "no dependency changes detected"})

    overall = overall_risk_level(changes)

    # Post or update comment
    comment_body = build_risk_comment(changes, overall, marker=COMMENT_MARKER, config=config)

    try:
        existing = gh.list_issue_comments(owner_login, repo_name, pr_number)
        bot_comment = None
        for c in existing:
            if c.get("user", {}).get("type") == "Bot" or (gh.is_app_authenticated and c.get("user", {}).get("login") == gh.app_slug):
                if COMMENT_MARKER in (c.get("body") or ""):
                    bot_comment = c
                    break
        if bot_comment:
            if bot_comment.get("body") != comment_body:
                gh.update_comment(owner_login, repo_name, bot_comment.get("id"), comment_body)
        else:
            gh.create_issue_comment(owner_login, repo_name, pr_number, comment_body)
    except Exception as e:
        # Non-fatal
        app.logger.exception("Failed to comment: %s", e)

    # Ensure labels
    desired_labels = set(config.base_labels)
    desired_labels.add(f"risk:{overall}")
    try:
        current_labels = gh.get_issue_labels(owner_login, repo_name, pr_number)
        current_names = {l.get("name") for l in current_labels}
        missing = list(desired_labels - current_names)
        if missing:
            gh.add_labels(owner_login, repo_name, pr_number, missing)
    except Exception as e:
        app.logger.exception("Failed to label PR: %s", e)

    # Auto-merge if allowed
    try:
        if config.auto_merge and overall in config.auto_merge_risk_levels:
            # Check required statuses
            sha = (pr.get("head") or {}).get("sha")
            if sha:
                status_ok = gh.combined_status_success(owner_login, repo_name, sha)
            else:
                status_ok = False
            if status_ok:
                # Avoid merging if PR is not mergeable or blocked
                pr_fresh = gh.get_pull_request(owner_login, repo_name, pr_number)
                if pr_fresh.get("mergeable_state") in {"clean", "has_hooks", "unstable"} and not pr_fresh.get("draft"):
                    gh.merge_pr(owner_login, repo_name, pr_number, method=config.merge_method, commit_title=None)
                    gh.add_labels(owner_login, repo_name, pr_number, [config.automerge_label])
                else:
                    app.logger.info("PR not mergeable state: %s", pr_fresh.get("mergeable_state"))
            else:
                app.logger.info("Statuses not successful; skip auto-merge")
    except Exception as e:
        app.logger.exception("Auto-merge failed: %s", e)

    return jsonify({"msg": "processed", "risk": overall, "deps": len(changes.get("dependencies", []))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))



def create_app():
    return app


@app.route('/analyze', methods=['POST'])
def _auto_stub_analyze():
    return 'Auto-generated stub for /analyze', 200
