import hmac
import os
import json
import time
from hashlib import sha256
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv
from .engine import Orchestrator
from .utils import sanitize_int

load_dotenv()

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").encode()
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "localhost")
BASE_PORT = int(os.getenv("BASE_PORT", "10080"))
CONTAINER_PORT = int(os.getenv("CONTAINER_PORT", "8000"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

ORCH = Orchestrator(
    base_port=BASE_PORT,
    container_port=CONTAINER_PORT,
    public_host=PUBLIC_HOST,
)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "public_host": PUBLIC_HOST})

@app.get("/environments")
def environments():
    return jsonify(ORCH.list_environments())

@app.post("/webhook")
def webhook():
    event = request.headers.get("X-GitHub-Event")
    sig = request.headers.get("X-Hub-Signature-256", "")
    raw = request.get_data() or b""

    if not WEBHOOK_SECRET:
        abort(400, description="WEBHOOK_SECRET not configured")

    mac = hmac.new(WEBHOOK_SECRET, msg=raw, digestmod=sha256)
    expected = f"sha256={mac.hexdigest()}"
    if not hmac.compare_digest(expected, sig or ""):
        abort(401, description="Invalid signature")

    if event != "pull_request":
        return jsonify({"ignored": True, "reason": f"event {event} not handled"})

    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    pr = payload.get("number")
    pr = sanitize_int(pr)

    if not pr:
        abort(400, description="Missing PR number")

    pr_data = payload.get("pull_request", {})

    if action in {"opened", "reopened", "synchronize", "edited"}:
        head = pr_data.get("head", {})
        base = pr_data.get("base", {})
        repo = head.get("repo", {}) or {}
        clone_url = repo.get("clone_url")
        ref = head.get("ref")
        sha = head.get("sha")
        pr_title = pr_data.get("title", "")
        pr_html_url = pr_data.get("html_url", "")
        repo_full_name = repo.get("full_name", "")

        if not clone_url or not ref:
            abort(400, description="Missing clone_url/ref in payload")

        info = ORCH.ensure_environment(
            pr_number=pr,
            clone_url=clone_url,
            ref=ref,
            sha=sha,
            gh_token=GITHUB_TOKEN,
            env_overrides={
                "PR_TITLE": pr_title,
                "PR_HTML_URL": pr_html_url,
                "REPO_FULL_NAME": repo_full_name,
                "PR_BASE": base.get("label", ""),
                "PR_HEAD": head.get("label", ""),
            },
        )
        return jsonify({"status": "created", **info})

    if action in {"closed"}:
        info = ORCH.teardown_environment(pr)
        return jsonify({"status": "deleted", **info})

    return jsonify({"ignored": True, "action": action})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

