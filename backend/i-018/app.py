import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, abort

from config import settings
from db import SessionLocal, init_db
from models import Repository, PullRequest, Commit, EventLog
from policy import evaluate_commits_against_policy
from provenance import extract_commit_record
from services.github_client import (
    verify_github_webhook_signature,
    parse_repo_full_name,
    github_get_pr_commits,
    github_get_commit,
    github_set_commit_status,
)

app = Flask(__name__)

# Initialize DB
init_db()


def get_or_create_repo(db, full_name: str):
    repo = db.query(Repository).filter_by(full_name=full_name).one_or_none()
    if not repo:
        repo = Repository(full_name=full_name)
        db.add(repo)
        db.commit()
        db.refresh(repo)
    return repo


@app.route("/health", methods=["GET"])  # Simple health check
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})


@app.route("/webhook/github", methods=["POST"])  # GitHub webhook endpoint
def github_webhook():
    db = SessionLocal()
    try:
        delivery_guid = request.headers.get("X-GitHub-Delivery", "")
        event_type = request.headers.get("X-GitHub-Event", "")

        # Verify signature if secret provided
        secret = settings.GITHUB_WEBHOOK_SECRET
        if secret:
            sig_header = request.headers.get("X-Hub-Signature-256")
            if not verify_github_webhook_signature(secret, request.data, sig_header):
                abort(401, description="Invalid webhook signature")

        payload = request.get_json(silent=True) or {}

        # Store event log
        event = EventLog(event_type=event_type, delivery_guid=delivery_guid, payload_json=json.dumps(payload))
        db.add(event)
        db.commit()

        # Determine repository
        repo_full_name = None
        if payload.get("repository", {}).get("full_name"):
            repo_full_name = payload["repository"]["full_name"]
        elif payload.get("pull_request", {}).get("base", {}).get("repo", {}).get("full_name"):
            repo_full_name = payload["pull_request"]["base"]["repo"]["full_name"]
        if not repo_full_name:
            return jsonify({"status": "ignored", "reason": "no repository in payload"}), 200

        repo = get_or_create_repo(db, repo_full_name)

        # Handle event types
        if event_type == "push":
            return handle_push_event(db, repo, payload)
        elif event_type == "pull_request":
            return handle_pull_request_event(db, repo, payload)
        else:
            return jsonify({"status": "ignored", "event": event_type}), 200
    finally:
        db.close()


def handle_push_event(db, repo, payload):
    ref = payload.get("ref")
    head_sha = payload.get("after")
    commits = payload.get("commits", [])
    head_commit_payload = payload.get("head_commit") or {}

    # Evaluate commits in the push; we may need to fetch verification via API
    owner, name = parse_repo_full_name(repo.full_name)
    collected = []

    # Ensure uniqueness of SHAs
    shas = []
    for c in commits:
        sha = c.get("id") or c.get("sha")
        if sha and sha not in shas:
            shas.append(sha)
    if head_sha and head_sha not in shas:
        shas.append(head_sha)

    for sha in shas:
        commit_payload = None
        if head_commit_payload and (head_commit_payload.get("id") == sha or head_commit_payload.get("sha") == sha):
            commit_payload = head_commit_payload
        # Fallback to API for verification and commit details
        api_commit = github_get_commit(owner, name, sha)
        record = extract_commit_record(repo_id=repo.id, pr_id=None, commit_payload=commit_payload, api_commit=api_commit)
        commit_model = upsert_commit_record(db, record)
        collected.append(commit_model)

    result = evaluate_commits_against_policy(collected)

    # Set status on head commit if token available
    if settings.GITHUB_TOKEN and head_sha:
        context = settings.STATUS_CONTEXT
        state = "success" if result["policy_passed"] else "failure"
        description = result.get("summary", "Provenance policy evaluation")[:140]
        target_url = settings.DASHBOARD_BASE_URL and f"{settings.DASHBOARD_BASE_URL}/commits/{head_sha}" or None
        github_set_commit_status(owner, name, head_sha, state, context, description, target_url)

    return jsonify({
        "status": "evaluated",
        "ref": ref,
        "head": head_sha,
        "policy_passed": result["policy_passed"],
        "summary": result.get("summary"),
        "violations": result.get("violations", []),
    }), 200


def handle_pull_request_event(db, repo, payload):
    action = payload.get("action")
    if action not in {"opened", "synchronize", "reopened", "edited", "ready_for_review"}:
        return jsonify({"status": "ignored", "action": action}), 200

    pr_data = payload.get("pull_request", {})
    pr_number = pr_data.get("number") or payload.get("number")
    head_sha = pr_data.get("head", {}).get("sha")

    # Ensure PR model exists/updated
    pr = db.query(PullRequest).filter_by(repo_id=repo.id, number=pr_number).one_or_none()
    if not pr:
        pr = PullRequest(repo_id=repo.id, number=pr_number, head_sha=head_sha, status="pending")
        db.add(pr)
        db.commit()
        db.refresh(pr)
    else:
        pr.head_sha = head_sha
        db.commit()

    owner, name = parse_repo_full_name(repo.full_name)

    # Fetch PR commits via API (requires token)
    commits_api = github_get_pr_commits(owner, name, pr_number)

    collected = []
    for c in commits_api:
        sha = c.get("sha")
        api_commit = github_get_commit(owner, name, sha)
        record = extract_commit_record(repo_id=repo.id, pr_id=pr.id, commit_payload=c, api_commit=api_commit)
        commit_model = upsert_commit_record(db, record)
        collected.append(commit_model)

    result = evaluate_commits_against_policy(collected)

    pr.status = "pass" if result["policy_passed"] else "fail"
    pr.last_evaluated_at = datetime.utcnow()
    db.commit()

    if settings.GITHUB_TOKEN and head_sha:
        context = settings.STATUS_CONTEXT
        state = "success" if result["policy_passed"] else "failure"
        description = result.get("summary", "Provenance policy evaluation")[:140]
        target_url = settings.DASHBOARD_BASE_URL and f"{settings.DASHBOARD_BASE_URL}/repos/{owner}/{name}/prs/{pr_number}/report" or None
        github_set_commit_status(owner, name, head_sha, state, context, description, target_url)

    return jsonify({
        "status": "evaluated",
        "pull_request": pr_number,
        "head": head_sha,
        "policy_passed": result["policy_passed"],
        "summary": result.get("summary"),
        "violations": result.get("violations", []),
    }), 200


def upsert_commit_record(db, record: dict):
    # record contains sha, repo_id, pr_id, etc.
    c = db.query(Commit).filter_by(sha=record["sha"], repo_id=record["repo_id"]).one_or_none()
    if not c:
        c = Commit(**record)
        db.add(c)
    else:
        for k, v in record.items():
            setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@app.route("/repos/<owner>/<repo>/prs/<int:number>/report", methods=["GET"])  # PR compliance report
def pr_report(owner, repo, number):
    db = SessionLocal()
    try:
        full_name = f"{owner}/{repo}"
        repo_m = db.query(Repository).filter_by(full_name=full_name).one_or_none()
        if not repo_m:
            abort(404)
        pr = db.query(PullRequest).filter_by(repo_id=repo_m.id, number=number).one_or_none()
        if not pr:
            abort(404)
        commits = db.query(Commit).filter_by(repo_id=repo_m.id, pr_id=pr.id).order_by(Commit.timestamp.asc()).all()
        result = evaluate_commits_against_policy(commits)
        return jsonify({
            "repository": full_name,
            "pull_request": number,
            "head_sha": pr.head_sha,
            "status": pr.status,
            "last_evaluated_at": pr.last_evaluated_at.isoformat() + "Z" if pr.last_evaluated_at else None,
            "policy_passed": result["policy_passed"],
            "summary": result.get("summary"),
            "violations": result.get("violations", []),
            "commits": [c.to_dict() for c in commits],
        })
    finally:
        db.close()


@app.route("/commits/<sha>", methods=["GET"])  # Commit record lookup
def commit_report(sha):
    db = SessionLocal()
    try:
        c = db.query(Commit).filter_by(sha=sha).one_or_none()
        if not c:
            abort(404)
        return jsonify(c.to_dict())
    finally:
        db.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))



def create_app():
    return app


@app.route('/verify-commit', methods=['POST'])
def _auto_stub_verify_commit():
    return 'Auto-generated stub for /verify-commit', 200


@app.route('/check-policy', methods=['POST'])
def _auto_stub_check_policy():
    return 'Auto-generated stub for /check-policy', 200
