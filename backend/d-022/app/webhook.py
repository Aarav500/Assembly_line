import hashlib
import hmac
import json
import os
import threading
from typing import Optional

import requests
from flask import Blueprint, abort, current_app, request

# Webhook to trigger smoke tests on PR events (optional, in addition to GitHub Actions)
webhook_bp = Blueprint("webhook", __name__)


def _hmac_sha256(secret: str, payload: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _verify_github_signature(req) -> bool:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        # If no secret configured, reject for safety
        return False
    theirs = req.headers.get("X-Hub-Signature-256", "")
    ours = _hmac_sha256(secret, req.data)
    # Timing-safe compare
    return hmac.compare_digest(ours, theirs)


def _extract_pr_context(event: dict) -> Optional[dict]:
    if event.get("pull_request"):
        pr = event["pull_request"]
        repo = event.get("repository", {})
        return {
            "owner": repo.get("owner", {}).get("login"),
            "repo": repo.get("name"),
            "sha": pr.get("head", {}).get("sha"),
            "number": pr.get("number"),
            "action": event.get("action"),
        }
    return None


def _set_commit_status(owner: str, repo: str, sha: str, state: str, description: str, target_url: Optional[str] = None):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        current_app.logger.warning("GITHUB_TOKEN not set; cannot set commit status")
        return
    url = f"https://api.github.com/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,  # error, failure, pending, success
        "description": description[:140],
        "context": "sandbox-smoke-tests",
    }
    if target_url:
        payload["target_url"] = target_url
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code >= 300:
            current_app.logger.error("Failed to set status: %s %s", r.status_code, r.text)
    except Exception as e:
        current_app.logger.exception("Error setting commit status: %s", e)


def _run_smoke_and_report(owner: str, repo: str, sha: str):
    from ci.smoke_runner import run_smoke_tests

    _set_commit_status(owner, repo, sha, "pending", "Running sandbox smoke tests")
    ok, report = run_smoke_tests()
    if ok:
        _set_commit_status(owner, repo, sha, "success", "All sandbox smoke tests passed")
    else:
        _set_commit_status(owner, repo, sha, "failure", f"Smoke tests failed: {report}")


@webhook_bp.post("/github")
def github_webhook():
    if not _verify_github_signature(request):
        abort(401, description="Invalid signature")
    try:
        event = request.get_json(force=True, silent=False)
    except Exception:
        abort(400, description="Invalid JSON payload")

    event_name = request.headers.get("X-GitHub-Event", "")
    if event_name != "pull_request":
        return {"ignored": True, "reason": f"event {event_name} not handled"}, 200

    ctx = _extract_pr_context(event)
    if not ctx or not ctx.get("owner") or not ctx.get("repo") or not ctx.get("sha"):
        abort(400, description="Missing required PR context")

    action = ctx.get("action")
    if action not in {"opened", "synchronize", "reopened"}:
        return {"ignored": True, "reason": f"action {action} not relevant"}, 200

    threading.Thread(target=_run_smoke_and_report, args=(ctx["owner"], ctx["repo"], ctx["sha"]), daemon=True).start()
    return {"ok": True, "message": "Smoke tests started"}, 202

