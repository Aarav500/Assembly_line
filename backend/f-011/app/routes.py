import json
from datetime import datetime
from flask import Blueprint, request, current_app
from .database import db
from .models import Deployment, MetricSample, Regression, MetricDefinition
from .github_client import GitHubClient
from .utils import parse_time

api_bp = Blueprint('api', __name__)


@api_bp.post('/deployments')
def create_deployment():
    data = request.get_json(force=True)
    service = data.get('service')
    env = data.get('env')
    version = data.get('version')
    commit_sha = data.get('commit_sha')
    deployed_at = parse_time(data.get('deployed_at')) or datetime.utcnow()

    if not service or not env:
        return {"error": "service and env are required"}, 400

    dep = Deployment(
        service=service,
        env=env,
        version=version,
        commit_sha=commit_sha,
        deployed_at=deployed_at,
    )

    # Optionally map commit to PRs via GitHub
    gh_repo = current_app.config.get('GITHUB_REPO', '')
    if gh_repo and '/' in gh_repo:
        owner, repo = gh_repo.split('/', 1)
        dep.repo_owner = owner
        dep.repo_name = repo

    gh = GitHubClient(current_app.config.get('GITHUB_TOKEN', ''), current_app.config.get('GITHUB_REPO', ''))
    if commit_sha and gh.enabled():
        prs = gh.get_prs_for_commit(commit_sha)
        if prs:
            pr_numbers = [p[0] for p in prs]
            pr_authors = [p[1] for p in prs]
            dep.pr_numbers = json.dumps(pr_numbers)
            dep.pr_authors = json.dumps(pr_authors)

    db.session.add(dep)
    db.session.commit()
    return {"id": dep.id, "service": dep.service, "env": dep.env, "deployed_at": dep.deployed_at.isoformat() + 'Z'}, 201


@api_bp.post('/metrics')
def ingest_metrics():
    payload = request.get_json(force=True)
    samples = payload if isinstance(payload, list) else [payload]
    created = 0
    for s in samples:
        service = s.get('service')
        env = s.get('env')
        metric_name = s.get('metric_name')
        value = s.get('value')
        timestamp = parse_time(s.get('timestamp')) or datetime.utcnow()
        version = s.get('version')
        if service and env and metric_name and value is not None:
            ms = MetricSample(service=service, env=env, metric_name=metric_name, value=float(value), timestamp=timestamp, version=version)
            db.session.add(ms)
            created += 1
    db.session.commit()
    return {"ingested": created}, 202


@api_bp.post('/metrics-def')
def upsert_metric_def():
    data = request.get_json(force=True)
    service = data.get('service')
    env = data.get('env')
    metric_name = data.get('metric_name')
    direction = data.get('direction', 'increase_bad')
    threshold_pct = data.get('threshold_pct')
    z_threshold = data.get('z_threshold')

    if not service or not env or not metric_name:
        return {"error": "service, env, metric_name required"}, 400

    md = MetricDefinition.query.filter_by(service=service, env=env, metric_name=metric_name).first()
    if not md:
        md = MetricDefinition(service=service, env=env, metric_name=metric_name)
    if direction in ('increase_bad', 'decrease_bad'):
        md.direction = direction
    if threshold_pct is not None:
        try:
            md.threshold_pct = float(threshold_pct)
        except Exception:
            pass
    if z_threshold is not None:
        try:
            md.z_threshold = float(z_threshold)
        except Exception:
            pass
    db.session.add(md)
    db.session.commit()
    return {"id": md.id, "service": md.service, "env": md.env, "metric_name": md.metric_name, "direction": md.direction, "threshold_pct": md.threshold_pct, "z_threshold": md.z_threshold}, 200


@api_bp.get('/regressions')
def list_regressions():
    status = request.args.get('status')
    q = Regression.query
    if status:
        q = q.filter_by(status=status)
    regs = q.order_by(Regression.detected_at.desc()).limit(200).all()
    result = []
    for r in regs:
        result.append({
            "id": r.id,
            "service": r.service,
            "env": r.env,
            "metric_name": r.metric_name,
            "deploy_id": r.deploy_id,
            "detected_at": r.detected_at.isoformat() + 'Z',
            "baseline_mean": r.baseline_mean,
            "post_mean": r.post_mean,
            "delta_pct": r.delta_pct,
            "z_score": r.z_score,
            "severity": r.severity,
            "status": r.status,
            "assigned_pr": r.assigned_pr,
            "assigned_user": r.assigned_user,
            "issue_url": r.issue_url,
        })
    return {"regressions": result}, 200


@api_bp.post('/regressions/<int:reg_id>/ack')
def ack_regression(reg_id: int):
    data = request.get_json(silent=True) or {}
    status = data.get('status', 'ack')
    if status not in ('ack', 'resolved', 'open'):
        return {"error": "invalid status"}, 400
    reg = Regression.query.get(reg_id)
    if not reg:
        return {"error": "not found"}, 404
    reg.status = status
    db.session.commit()
    return {"id": reg.id, "status": reg.status}, 200

