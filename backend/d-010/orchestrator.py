import logging
import threading
import time
import uuid
from typing import Dict, Optional, List

from metrics import MetricSample, MetricsWindow
from models import CanaryDeployment, CanaryConfig, DeploymentStatus, Event
from providers.base import TrafficRouter

logger = logging.getLogger(__name__)


class CanaryOrchestrator:
    def __init__(self, router: TrafficRouter):
        self.router = router
        self._deployments: Dict[str, CanaryDeployment] = {}
        self._lock = threading.RLock()

    def create_deployment(self, payload: dict) -> CanaryDeployment:
        service = payload.get("service_name")
        new_version = payload.get("new_version")
        baseline_version = payload.get("baseline_version") or "stable"
        if not service or not new_version:
            raise ValueError("service_name and new_version are required")

        strategy = payload.get("strategy") or {}
        policy = payload.get("policy") or {}

        cfg = CanaryConfig.from_dict(strategy, policy)

        dep_id = str(uuid.uuid4())
        dep = CanaryDeployment(
            id=dep_id,
            service_name=service,
            new_version=new_version,
            baseline_version=baseline_version,
            config=cfg,
            status=DeploymentStatus.RUNNING,
        )
        dep.metrics_window = MetricsWindow(window_sec=cfg.sample_window_sec)
        dep.history.append(Event(ts=time.time(), level="info", msg="created"))

        with self._lock:
            self._deployments[dep_id] = dep

        # Apply initial traffic split
        self.router.set_traffic_split(
            service_name=service,
            baseline_version=baseline_version,
            canary_version=new_version,
            canary_weight=cfg.initial_weight,
        )
        dep.current_weight = cfg.initial_weight
        dep.current_step = 0
        dep.last_step_started_at = time.time()
        dep.history.append(Event(ts=time.time(), level="info", msg=f"canary started at {cfg.initial_weight}%"))
        logger.info("Started canary %s for %s -> %s at %d%%", dep.id, service, new_version, cfg.initial_weight)
        return dep

    def list_deployments(self) -> List[CanaryDeployment]:
        with self._lock:
            return list(self._deployments.values())

    def get(self, dep_id: str) -> Optional[CanaryDeployment]:
        with self._lock:
            return self._deployments.get(dep_id)

    def cancel(self, dep_id: str) -> Optional[CanaryDeployment]:
        with self._lock:
            dep = self._deployments.get(dep_id)
            if not dep:
                return None
            if dep.status in (DeploymentStatus.PROMOTED, DeploymentStatus.ROLLED_BACK, DeploymentStatus.CANCELLED, DeploymentStatus.FAILED):
                return dep
            dep.status = DeploymentStatus.CANCELLED
        # Route all traffic back to baseline
        try:
            self.router.rollback(dep.service_name, dep.baseline_version)
        except Exception:
            logger.exception("router.rollback failed")
        dep.history.append(Event(ts=time.time(), level="warn", msg="cancelled"))
        return dep

    def add_metrics(self, dep_id: str, metrics: dict, ts: Optional[float] = None):
        dep = self.get(dep_id)
        if dep is None:
            raise KeyError("deployment not found")
        if dep.status != DeploymentStatus.RUNNING:
            raise ValueError("deployment not accepting metrics in status %s" % dep.status.value)
        sample = MetricSample.from_dict(metrics, ts)
        dep.metrics_window.add_sample(sample)
        dep.last_metrics_at = sample.timestamp

    def tick(self):
        now = time.time()
        with self._lock:
            deps = list(self._deployments.values())
        for dep in deps:
            if dep.status != DeploymentStatus.RUNNING:
                continue
            # Respect the interval between steps
            if dep.last_step_started_at is None:
                dep.last_step_started_at = now
            elapsed = now - dep.last_step_started_at
            if elapsed < dep.config.interval_sec:
                continue
            # Evaluate metrics and decide promotion/rollback
            self._evaluate(dep)

    def _evaluate(self, dep: CanaryDeployment):
        cfg = dep.config
        window = dep.metrics_window
        if not window:
            dep.metrics_window = MetricsWindow(window_sec=cfg.sample_window_sec)
            window = dep.metrics_window

        sufficiency = window.is_sufficient(cfg.min_samples, cfg.min_requests)
        if not sufficiency:
            dep.history.append(Event(ts=time.time(), level="debug", msg="insufficient_metrics_window"))
            # Extend step waiting for more metrics; do not reset timer to avoid spinning
            dep.last_step_started_at = time.time()
            return

        passed, reasons, aggregates = window.evaluate(cfg)
        dep.last_aggregates = aggregates
        if passed:
            # Promote step
            old = dep.current_weight
            new_weight = min(100, old + cfg.step_weight)
            try:
                self.router.set_traffic_split(
                    service_name=dep.service_name,
                    baseline_version=dep.baseline_version,
                    canary_version=dep.new_version,
                    canary_weight=new_weight,
                )
                dep.current_weight = new_weight
                dep.current_step += 1
                dep.last_step_started_at = time.time()
                window.reset()
                dep.fail_count = 0
                dep.history.append(Event(ts=time.time(), level="info", msg=f"promoted step to {new_weight}%"))
                logger.info("%s: promoted to %d%% (step %d)", dep.id, new_weight, dep.current_step)
            except Exception as e:
                dep.status = DeploymentStatus.FAILED
                dep.history.append(Event(ts=time.time(), level="error", msg=f"router_error: {e}"))
                logger.exception("router.set_traffic_split failed for %s", dep.id)
                return

            if new_weight >= 100 or dep.current_step >= cfg.max_steps:
                try:
                    self.router.promote(dep.service_name, dep.new_version)
                except Exception:
                    logger.exception("router.promote failed for %s", dep.id)
                dep.status = DeploymentStatus.PROMOTED
                dep.completed_at = time.time()
                dep.history.append(Event(ts=time.time(), level="info", msg="deployment promoted to 100%"))
                logger.info("%s: deployment promoted to 100%%", dep.id)
        else:
            dep.fail_count += 1
            dep.history.append(Event(ts=time.time(), level="warn", msg=f"policy_violation: {', '.join(reasons)}"))
            logger.warning("%s: policy violation: %s (fail_count=%d)", dep.id, reasons, dep.fail_count)
            if cfg.rollback_on_failure and dep.fail_count >= cfg.max_consecutive_failures:
                try:
                    self.router.rollback(dep.service_name, dep.baseline_version)
                except Exception:
                    logger.exception("router.rollback failed for %s", dep.id)
                dep.status = DeploymentStatus.ROLLED_BACK
                dep.completed_at = time.time()
                dep.history.append(Event(ts=time.time(), level="error", msg="rolled back due to policy violations"))
                logger.error("%s: rolled back due to policy violations", dep.id)
            else:
                # Keep at same weight, reset window and wait another interval
                dep.last_step_started_at = time.time()
                window.reset()


