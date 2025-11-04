import json
import logging
import os
from flask import Flask, request, jsonify

from .config import Settings
from .utils.signature import verify_github_signature
from .orchestrator.cleanup import cleanup_for_pr


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)

    app_settings = settings or Settings.from_env()

    # Configure logging
    log_level = logging.DEBUG if app_settings.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    logger = logging.getLogger("cleanup-app")
    logger.info("Cleanup service starting. Dry-run=%s", app_settings.dry_run)

    @app.route("/healthz", methods=["GET"])  # Basic health endpoint
    def healthz():
        return jsonify({"status": "ok", "dry_run": app_settings.dry_run}), 200

    @app.route("/webhook", methods=["POST"])  # GitHub webhook endpoint
    def webhook():
        raw_body = request.get_data()  # bytes, required for signature

        # Signature verification
        if not app_settings.insecure_disable_signature_verification:
            signature = request.headers.get("X-Hub-Signature-256")
            secret = app_settings.github_webhook_secret
            if not secret:
                return jsonify({"error": "Missing GITHUB_WEBHOOK_SECRET"}), 400
            if not signature or not verify_github_signature(secret, raw_body, signature):
                logger.warning("Invalid or missing webhook signature")
                return jsonify({"error": "Invalid signature"}), 403
        else:
            logger.warning("Signature verification is disabled! Do not use in production.")

        event = request.headers.get("X-GitHub-Event")
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400

        if event != "pull_request":
            # No-op for other events
            return jsonify({"status": "ignored", "reason": f"event {event} not handled"}), 200

        action = payload.get("action")
        pr = payload.get("pull_request", {})

        if action != "closed":
            return jsonify({"status": "ignored", "reason": f"pull_request action {action} not handled"}), 200

        # Build context from payload
        repo = payload.get("repository", {})
        repo_owner = (repo.get("owner") or {}).get("login")
        repo_name = repo.get("name")
        pr_number = pr.get("number")
        merged = pr.get("merged", False)
        head = pr.get("head", {})
        base = pr.get("base", {})
        branch = head.get("ref")
        sha = head.get("sha")
        title = pr.get("title")

        if not (repo_owner and repo_name and pr_number):
            return jsonify({"error": "Missing repository or PR number info in payload"}), 400

        ctx = {
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "repo_full_name": f"{repo_owner}/{repo_name}",
            "pr_number": int(pr_number),
            "pr_merged": bool(merged),
            "branch": branch,
            "head_sha": sha,
            "title": title,
        }

        logger.info(
            "Received PR closed webhook for %s PR#%s (merged=%s)", ctx["repo_full_name"], ctx["pr_number"], ctx["pr_merged"]
        )

        # Execute cleanup orchestrator
        try:
            results = cleanup_for_pr(ctx, app_settings)
            status_code = 200
            return jsonify({
                "status": "ok",
                "dry_run": app_settings.dry_run,
                "context": {
                    "repo": ctx["repo_full_name"],
                    "pr": ctx["pr_number"],
                    "merged": ctx["pr_merged"],
                },
                "results": results,
            }), status_code
        except Exception as e:
            logger.exception("Cleanup failed: %s", e)
            return jsonify({"status": "error", "error": str(e)}), 500

    return app


# Allow running via `python -m app.app`
if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

