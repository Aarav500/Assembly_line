import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hmac
import hashlib
import logging
import os
from flask import Flask, request, jsonify

from config import settings
from service.releaser import ReleaseManager

app = Flask(__name__)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

release_manager = ReleaseManager()


def verify_github_signature(req):
    secret = settings.WEBHOOK_SECRET
    if not secret:
        # No verification if secret is not configured
        return True
    signature = req.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), req.data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", signature)


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/webhook", methods=["POST"]) 
def webhook():
    if not verify_github_signature(request):
        return jsonify({"error": "Invalid signature"}), 401

    event = request.headers.get("X-GitHub-Event")
    payload = request.get_json(silent=True) or {}

    if event == "ping":
        return jsonify({"msg": "pong"})

    try:
        if event == "push":
            ref = payload.get("ref")
            if ref == f"refs/heads/{settings.DEFAULT_BRANCH}":
                repo_full_name = payload.get("repository", {}).get("full_name") or settings.REPO_FULL_NAME
                commits = payload.get("commits", [])
                head_sha = payload.get("after")
                result = release_manager.handle_commits_event(repo_full_name, commits, head_sha)
                return jsonify(result)
            else:
                return jsonify({"skipped": True, "reason": "Not default branch"})

        if event == "pull_request":
            action = payload.get("action")
            pr = payload.get("pull_request", {})
            merged = pr.get("merged", False)
            base_ref = pr.get("base", {}).get("ref")
            if action == "closed" and merged and base_ref == settings.DEFAULT_BRANCH:
                repo_full_name = payload.get("repository", {}).get("full_name") or settings.REPO_FULL_NAME
                result = release_manager.handle_pull_request_merged(repo_full_name, pr)
                return jsonify(result)
            else:
                return jsonify({"skipped": True, "reason": "PR not merged to default branch"})

        return jsonify({"skipped": True, "reason": f"Unhandled event {event}"})
    except Exception as e:
        logger.exception("Error handling webhook: %s", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))



def create_app():
    return app


@app.route('/api/parse-commits', methods=['POST'])
def _auto_stub_api_parse_commits():
    return 'Auto-generated stub for /api/parse-commits', 200


@app.route('/api/generate-release', methods=['POST'])
def _auto_stub_api_generate_release():
    return 'Auto-generated stub for /api/generate-release', 200
