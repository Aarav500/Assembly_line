from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional

from .storage import Storage
from .notifiers import NotifierManager
from .config import Config, FlowConfig


class AlertManager:
    def __init__(self, storage: Storage, notifiers: NotifierManager, config: Config):
        self.storage = storage
        self.notifiers = notifiers
        self._config = config

    def set_config(self, cfg: Config):
        self._config = cfg

    def evaluate_and_alert(self, flow: FlowConfig, success: bool, error_summary: Optional[str]):
        state = self.storage.get_or_create_flow_state(flow.id)
        now = datetime.utcnow()
        cooldown = timedelta(seconds=self._config.alerting.default_cooldown_sec)

        transitioned_to_failure = (state.last_status in ("unknown", "success")) and not success
        transitioned_to_success = (state.last_status == "failure") and success

        consecutive_failures = state.consecutive_failures
        if success:
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        should_alert_failure = False
        reason = None
        if not success:
            if consecutive_failures >= flow.fail_threshold:
                if transitioned_to_failure:
                    should_alert_failure = True
                    reason = "transition"
                else:
                    # still failing; check cooldown
                    if not state.last_alerted_at or (now - state.last_alerted_at) >= cooldown:
                        should_alert_failure = True
                        reason = "cooldown"

        # Fire alerts
        if should_alert_failure:
            title = f"Flow FAILED: {flow.name}"
            message = error_summary or f"Flow {flow.id} encountered an error."
            channels = flow.alert_channels or self._config.alerting.notifiers
            sent = self.notifiers.send(channels, title, message)
            self.storage.create_alert_event(flow.id, flow.name, "failure", flow.severity, message, sent)
            last_alerted_at = now
        elif transitioned_to_success:
            title = f"Flow RECOVERED: {flow.name}"
            message = "Flow is back to passing."
            channels = flow.alert_channels or self._config.alerting.notifiers
            sent = self.notifiers.send(channels, title, message)
            self.storage.create_alert_event(flow.id, flow.name, "recovery", flow.severity, message, sent)
            last_alerted_at = state.last_alerted_at
        else:
            last_alerted_at = state.last_alerted_at

        # Update state
        self.storage.update_flow_state(
            flow_id=flow.id,
            last_status='success' if success else 'failure',
            consecutive_failures=consecutive_failures,
            last_alerted_at=last_alerted_at,
        )

