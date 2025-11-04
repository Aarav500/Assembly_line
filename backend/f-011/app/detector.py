import json
import math
import time
from datetime import datetime, timedelta
from sqlalchemy import func
from .database import db
from .models import Deployment, MetricSample, Baseline, Regression, MetricDefinition
from .github_client import GitHubClient
from .triage import Triager


class Detector:
    def __init__(self, app):
        self.app = app
        self.poll_seconds = int(app.config.get('DETECTOR_POLL_SECONDS', 30))
        self.default_pct_th = float(app.config.get('REGRESSION_PCT_THRESHOLD', 0.2))
        self.default_z_th = float(app.config.get('REGRESSION_Z_THRESHOLD', 2.0))
        self.baseline_window = int(app.config.get('BASELINE_WINDOW_MIN', 60))
        self.eval_window = int(app.config.get('EVAL_WINDOW_MIN', 10))
        self.baseline_min_samples = int(app.config.get('BASELINE_MIN_SAMPLES', 30))
        self.eval_min_samples = int(app.config.get('EVAL_MIN_SAMPLES', 5))
        self.gh = GitHubClient(app.config.get('GITHUB_TOKEN', ''), app.config.get('GITHUB_REPO', ''))
        self.triager = Triager(self.gh)

    def run_forever(self):
        while True:
            try:
                self.run_once()
            except Exception as e:
                # In production you would log this
                pass
            time.sleep(self.poll_seconds)

    def run_once(self):
        now = datetime.utcnow()
        # Consider deployments where eval window has elapsed within last few hours
        cutoff = now - timedelta(hours=24)
        deployments = (Deployment.query
                        .filter(Deployment.deployed_at >= cutoff)
                        .order_by(Deployment.deployed_at.desc())
                        .all())
        for dep in deployments:
            if now < dep.deployed_at + timedelta(minutes=self.eval_window):
                continue  # wait until enough data collected
            self._evaluate_deployment(dep)

    def _get_metric_def(self, service, env, metric_name) -> MetricDefinition:
        md = MetricDefinition.query.filter_by(service=service, env=env, metric_name=metric_name).first()
        return md

    def _thresholds(self, md: MetricDefinition):
        pct = md.threshold_pct if (md and md.threshold_pct is not None) else self.default_pct_th
        z = md.z_threshold if (md and md.z_threshold is not None) else self.default_z_th
        direction = md.direction if md else 'increase_bad'
        return pct, z, direction

    def _evaluate_deployment(self, dep: Deployment):
        # Find metrics that have data in the eval window after deployment
        eval_start = dep.deployed_at
        eval_end = dep.deployed_at + timedelta(minutes=self.eval_window)

        metric_names = db.session.query(MetricSample.metric_name) \
            .filter(MetricSample.service == dep.service, MetricSample.env == dep.env, MetricSample.timestamp >= eval_start, MetricSample.timestamp <= eval_end) \
            .distinct().all()
        metric_names = [m[0] for m in metric_names]

        if not metric_names:
            return

        # Baseline window before deployment
        base_start = dep.deployed_at - timedelta(minutes=self.baseline_window)
        base_end = dep.deployed_at

        for metric in metric_names:
            # Skip if regression already recorded for this deploy+metric
            existing = Regression.query.filter_by(service=dep.service, env=dep.env, metric_name=metric, deploy_id=dep.id).first()
            if existing:
                continue

            base_q = MetricSample.query.filter(
                MetricSample.service == dep.service,
                MetricSample.env == dep.env,
                MetricSample.metric_name == metric,
                MetricSample.timestamp >= base_start,
                MetricSample.timestamp < base_end,
            )
            eval_q = MetricSample.query.filter(
                MetricSample.service == dep.service,
                MetricSample.env == dep.env,
                MetricSample.metric_name == metric,
                MetricSample.timestamp >= eval_start,
                MetricSample.timestamp <= eval_end,
            )

            base_count = base_q.count()
            eval_count = eval_q.count()
            if base_count < self.baseline_min_samples or eval_count < self.eval_min_samples:
                continue

            # Compute mean/std for baseline and mean for eval
            base_vals = [row[0] for row in db.session.query(MetricSample.value).filter(base_q._criterion).all()]
            eval_vals = [row[0] for row in db.session.query(MetricSample.value).filter(eval_q._criterion).all()]

            base_mean = sum(base_vals) / len(base_vals)
            variance = sum((x - base_mean) ** 2 for x in base_vals) / max(len(base_vals) - 1, 1)
            base_std = math.sqrt(max(variance, 0.0))
            post_mean = sum(eval_vals) / len(eval_vals)

            epsilon = 1e-9
            delta = post_mean - base_mean
            delta_pct = delta / (abs(base_mean) + epsilon)
            z = (delta / (base_std + epsilon)) if base_std > 0 else float('inf') if abs(delta) > 0 else 0.0

            md = self._get_metric_def(dep.service, dep.env, metric)
            pct_th, z_th, direction = self._thresholds(md)

            is_regression = False
            if direction == 'increase_bad':
                is_regression = (delta_pct >= pct_th) and (z >= z_th)
            else:  # decrease_bad
                is_regression = (delta_pct <= -pct_th) and (-z >= z_th)

            # Store baseline regardless for traceability
            baseline = Baseline(
                service=dep.service,
                env=dep.env,
                metric_name=metric,
                deploy_id=dep.id,
                mean=base_mean,
                std=base_std,
                window_start=base_start,
                window_end=base_end,
            )
            db.session.add(baseline)
            db.session.commit()

            if is_regression:
                severity = abs(delta_pct)
                reg = Regression(
                    service=dep.service,
                    env=dep.env,
                    metric_name=metric,
                    deploy_id=dep.id,
                    baseline_mean=base_mean,
                    post_mean=post_mean,
                    delta_pct=delta_pct,
                    z_score=z,
                    severity=severity,
                    status='open'
                )
                db.session.add(reg)
                db.session.commit()

                # Attempt triage
                self.triager.triage(reg, dep)

