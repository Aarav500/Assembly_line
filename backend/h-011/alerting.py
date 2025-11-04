import json
import os
import requests
from datetime import datetime
from storage import Storage


def iso_now():
    return datetime.utcnow().isoformat() + "Z"


class AlertManager:
    def __init__(self):
        self.storage = Storage(os.environ.get("DRIFT_DATA_DIR", "data"))

    def _post_slack(self, webhook_url, text, blocks=None):
        if not webhook_url:
            return False
        payload = {"text": text}
        if blocks:
            payload["blocks"] = blocks
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True

    def send_drift_alert(self, alerts_cfg, entry):
        # Record event
        event = {
            "timestamp": iso_now(),
            "type": "drift_detected",
            "batch_id": entry.get("batch_id"),
            "drifted_features": entry.get("drifted_features", []),
            "size": entry.get("size"),
            "meta": entry.get("meta", {}),
        }
        self.storage.record_event(event)

        # Slack
        slack_url = alerts_cfg.get("slack_webhook_url") or os.environ.get("SLACK_WEBHOOK_URL")
        if slack_url:
            drift_feats = entry.get("drifted_features", [])
            text = (
                f"Data drift detected in batch {entry.get('batch_id')} with {len(drift_feats)} feature(s): "
                + ", ".join(drift_feats)
            )
            # Build a concise block with top 5 metrics
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": f"Size: {entry.get('size')} | Time: {entry.get('timestamp')}"}
                ]}
            ]
            # Show top metrics for first few features
            metrics = entry.get("metrics_by_feature", {})
            for f in drift_feats[:5]:
                m = metrics.get(f, {})
                if m.get("type") == "numeric":
                    desc = f"psi={m.get('psi')}, ks={m.get('ks')}, z={m.get('zscore_mean_shift')}"
                else:
                    desc = f"psi={m.get('psi')}, jsd={m.get('jsd')}, new_ratio={m.get('new_category_ratio')}"
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"• {f}: {desc}"}})
            try:
                self._post_slack(slack_url, text, blocks=blocks)
            except Exception as e:
                print(f"[alerting] Slack notification failed: {e}")

