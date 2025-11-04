import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler

from config import AppConfig, ScalingPolicy
from providers import provider_from_name
from metrics import metrics_source_from_config
from util.time_windows import get_active_window, get_next_window_start

logger = logging.getLogger(__name__)


class AutoScaler:
    def __init__(self, config: AppConfig, interval_seconds: int = 30):
        self._lock = threading.RLock()
        self._config = config
        self._interval_seconds = interval_seconds
        self._scheduler = BackgroundScheduler()
        self._scheduler.add_job(self.reconcile_once, 'interval', seconds=self._interval_seconds, id='reconcile')
        self._providers = {}
        self._metrics = {}
        self._state = {
            'policies': {},  # name -> state
            'last_reconcile': None,
        }
        self._init_resources()

    def _init_resources(self):
        with self._lock:
            self._providers.clear()
            self._metrics.clear()
            for p in self._config.policies:
                self._providers[p.name] = provider_from_name(p.provider, p.provider_params)
                self._metrics[p.name] = metrics_source_from_config(p.metrics)
                self._state['policies'][p.name] = {
                    'last_scale': None,
                    'last_desired': None,
                    'last_queue': None,
                    'cooldown_until': None,
                    'last_error': None,
                }

    def start(self):
        self._scheduler.start()
        logger.info("AutoScaler started with reconcile interval=%ss", self._interval_seconds)

    def stop(self):
        self._scheduler.shutdown(wait=False)
        logger.info("AutoScaler stopped")

    def update_config(self, new_config: AppConfig):
        with self._lock:
            self._config = new_config
            self._init_resources()
            logger.info("Config updated: %d policies", len(self._config.policies))

    def get_config(self) -> AppConfig:
        with self._lock:
            return self._config

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            out = {'policies': {}, 'last_reconcile': self._state['last_reconcile']}
            for p in self._config.policies:
                prov = self._providers.get(p.name)
                try:
                    current = prov.get_current_gpus(p.pool_id)
                except Exception as e:
                    current = None
                st = self._state['policies'].get(p.name, {})
                out['policies'][p.name] = {
                    'pool_id': p.pool_id,
                    'current_gpus': current,
                    'last_desired': st.get('last_desired'),
                    'last_queue': st.get('last_queue'),
                    'last_scale': st.get('last_scale'),
                    'cooldown_until': st.get('cooldown_until'),
                    'last_error': st.get('last_error'),
                }
            return out

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            snap = {}
            for p in self._config.policies:
                try:
                    snap[p.name] = {
                        'queue_depth': self._metrics[p.name].get_queue_depth(p.metrics.metric_id),
                    }
                except Exception as e:
                    snap[p.name] = {'error': str(e)}
            return snap

    def scale_now(self, policy_name: str, target_gpus: int):
        with self._lock:
            policy = self._find_policy(policy_name)
            prov = self._providers[policy.name]
            current = prov.get_current_gpus(policy.pool_id)
            target = max(min(target_gpus, policy.max_gpus), policy.min_gpus)
            logger.info("Manual scale %s: %s -> %s GPUs", policy.name, current, target)
            prov.scale_pool_to_gpus(policy.pool_id, target)
            st = self._state['policies'][policy.name]
            now = datetime.now(timezone.utc)
            st['last_scale'] = now.isoformat()
            st['last_desired'] = target
            st['cooldown_until'] = (now + timedelta(seconds=policy.cooldown_seconds)).isoformat()

    def reconcile_once(self):
        with self._lock:
            now = datetime.now(timezone.utc)
            self._state['last_reconcile'] = now.isoformat()
            for policy in self._config.policies:
                try:
                    self._reconcile_policy(policy, now)
                except Exception as e:
                    logger.exception("Reconcile error for policy %s", policy.name)
                    self._state['policies'][policy.name]['last_error'] = str(e)

    def _reconcile_policy(self, policy: ScalingPolicy, now: datetime):
        prov = self._providers[policy.name]
        metrics = self._metrics[policy.name]
        st = self._state['policies'][policy.name]

        queue_depth = 0
        try:
            queue_depth = metrics.get_queue_depth(policy.metrics.metric_id)
            st['last_queue'] = queue_depth
        except Exception as e:
            st['last_error'] = f"metrics: {e}"
            logger.warning("Metrics error for %s: %s", policy.name, e)

        try:
            current = prov.get_current_gpus(policy.pool_id)
        except Exception as e:
            st['last_error'] = f"provider: {e}"
            logger.warning("Provider error for %s: %s", policy.name, e)
            return

        desired = self._compute_desired_gpus(policy, now, queue_depth)
        st['last_desired'] = desired

        cooldown_until = self._parse_time(st.get('cooldown_until'))
        if cooldown_until and now < cooldown_until:
            logger.debug("Policy %s in cooldown until %s", policy.name, cooldown_until)
            return

        if desired == current:
            return

        # Step limit
        step = policy.scale_step_gpus
        if desired > current:
            target = min(current + step, desired)
        else:
            target = max(current - step, desired)

        if target == current:
            return

        logger.info("Scaling %s pool=%s from %s -> %s GPUs (desired=%s, queue=%s)", policy.name, policy.pool_id, current, target, desired, queue_depth)
        prov.scale_pool_to_gpus(policy.pool_id, target)
        st['last_scale'] = now.isoformat()
        st['cooldown_until'] = (now + timedelta(seconds=policy.cooldown_seconds)).isoformat()

    def _compute_desired_gpus(self, policy: ScalingPolicy, now: datetime, queue_depth: int) -> int:
        # Base desired based on queue
        per_gpu = max(policy.target_queue_per_gpu, 1)
        base = (queue_depth + per_gpu - 1) // per_gpu

        # Apply batch window min_gpus
        active_window = get_active_window(now, policy.batch_windows)
        if active_window is not None:
            base = max(base, active_window.min_gpus)
        else:
            # Pre-scale if within lead time of next window
            nxt = get_next_window_start(now, policy.batch_windows)
            if nxt is not None and nxt.lead_minutes and nxt.start_dt is not None:
                lead_td = timedelta(minutes=nxt.lead_minutes)
                if now >= (nxt.start_dt - lead_td) and now <= nxt.start_dt:
                    base = max(base, nxt.min_gpus)

        # Clamp
        base = max(base, policy.min_gpus)
        base = min(base, policy.max_gpus)
        return base

    def _find_policy(self, name: str) -> ScalingPolicy:
        for p in self._config.policies:
            if p.name == name:
                return p
        raise ValueError(f"Unknown policy: {name}")

    @staticmethod
    def _parse_time(ts: str):
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

