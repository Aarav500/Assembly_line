from datetime import datetime
from .database import db
from sqlalchemy.dialects.sqlite import JSON


class Deployment(db.Model):
    __tablename__ = 'deployments'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(128), nullable=False)
    env = db.Column(db.String(64), nullable=False)
    version = db.Column(db.String(128), nullable=True)
    commit_sha = db.Column(db.String(64), nullable=True, index=True)
    repo_owner = db.Column(db.String(128), nullable=True)
    repo_name = db.Column(db.String(128), nullable=True)
    pr_numbers = db.Column(db.Text, nullable=True)  # JSON stringified list
    pr_authors = db.Column(db.Text, nullable=True)  # JSON stringified list
    deployed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index('idx_deploy_service_env_time', 'service', 'env', 'deployed_at'),
    )


class MetricDefinition(db.Model):
    __tablename__ = 'metric_definitions'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(128), nullable=False)
    env = db.Column(db.String(64), nullable=False)
    metric_name = db.Column(db.String(128), nullable=False)
    direction = db.Column(db.String(16), nullable=False, default='increase_bad')  # 'increase_bad' or 'decrease_bad'
    threshold_pct = db.Column(db.Float, nullable=True)
    z_threshold = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('service', 'env', 'metric_name', name='uq_metric_def'),
    )


class MetricSample(db.Model):
    __tablename__ = 'metric_samples'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(128), nullable=False)
    env = db.Column(db.String(64), nullable=False)
    metric_name = db.Column(db.String(128), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    value = db.Column(db.Float, nullable=False)
    version = db.Column(db.String(128), nullable=True)

    __table_args__ = (
        db.Index('idx_metric_service_env_time', 'service', 'env', 'timestamp'),
        db.Index('idx_metric_service_env_name_time', 'service', 'env', 'metric_name', 'timestamp'),
    )


class Baseline(db.Model):
    __tablename__ = 'baselines'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(128), nullable=False)
    env = db.Column(db.String(64), nullable=False)
    metric_name = db.Column(db.String(128), nullable=False)
    deploy_id = db.Column(db.Integer, db.ForeignKey('deployments.id'), nullable=False)
    mean = db.Column(db.Float, nullable=False)
    std = db.Column(db.Float, nullable=False)
    window_start = db.Column(db.DateTime, nullable=False)
    window_end = db.Column(db.DateTime, nullable=False)
    computed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_baseline_service_env_metric_deploy', 'service', 'env', 'metric_name', 'deploy_id'),
    )


class Regression(db.Model):
    __tablename__ = 'regressions'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(128), nullable=False)
    env = db.Column(db.String(64), nullable=False)
    metric_name = db.Column(db.String(128), nullable=False)
    deploy_id = db.Column(db.Integer, db.ForeignKey('deployments.id'), nullable=False)
    detected_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    baseline_mean = db.Column(db.Float, nullable=False)
    post_mean = db.Column(db.Float, nullable=False)
    delta_pct = db.Column(db.Float, nullable=False)
    z_score = db.Column(db.Float, nullable=False)
    severity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='open')  # open, ack, resolved
    assigned_pr = db.Column(db.Integer, nullable=True)
    assigned_user = db.Column(db.String(128), nullable=True)
    issue_url = db.Column(db.String(512), nullable=True)

    __table_args__ = (
        db.Index('idx_reg_service_env_metric_deploy', 'service', 'env', 'metric_name', 'deploy_id'),
        db.Index('idx_reg_status', 'status'),
    )

