import os
import json
import threading
from datetime import datetime


class Storage:
    def __init__(self, root_dir="data"):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self._lock = threading.Lock()
        self.config_path = os.path.join(self.root_dir, "config.json")
        self.baseline_path = os.path.join(self.root_dir, "baseline.json")
        self.history_path = os.path.join(self.root_dir, "history.jsonl")
        self.events_path = os.path.join(self.root_dir, "events.jsonl")
        # Initialize default config if absent
        if not os.path.exists(self.config_path):
            try:
                with open(os.path.join(os.path.dirname(__file__), 'config_default.json'), 'r') as f:
                    default_cfg = json.load(f)
            except Exception:
                default_cfg = {
                    "thresholds": {
                        "numeric_psi_threshold": 0.2,
                        "numeric_ks_threshold": 0.1,
                        "numeric_zscore_mean_shift_threshold": 3.0,
                        "categorical_psi_threshold": 0.2,
                        "categorical_jsd_threshold": 0.1,
                        "categorical_new_category_ratio_threshold": 0.05
                    },
                    "alerts": {
                        "slack_webhook_url": None
                    }
                }
            self.save_config(default_cfg)

    def _atomic_write(self, path, data_bytes):
        tmp = path + ".tmp"
        with open(tmp, 'wb') as f:
            f.write(data_bytes)
        os.replace(tmp, path)

    def load_config(self):
        with self._lock:
            if not os.path.exists(self.config_path):
                return {}
            with open(self.config_path, 'r') as f:
                return json.load(f)

    def save_config(self, cfg):
        with self._lock:
            self._atomic_write(self.config_path, json.dumps(cfg, indent=2).encode('utf-8'))

    def get_baseline(self):
        with self._lock:
            if not os.path.exists(self.baseline_path):
                return None
            with open(self.baseline_path, 'r') as f:
                try:
                    return json.load(f)
                except Exception:
                    return None

    def save_baseline(self, baseline):
        with self._lock:
            self._atomic_write(self.baseline_path, json.dumps(baseline, indent=2).encode('utf-8'))

    def append_history(self, entry):
        with self._lock:
            with open(self.history_path, 'a') as f:
                f.write(json.dumps(entry) + "\n")

    def get_history(self, limit=50):
        items = []
        with self._lock:
            if not os.path.exists(self.history_path):
                return []
            with open(self.history_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        continue
        return items[-limit:]

    def record_event(self, event):
        with self._lock:
            with open(self.events_path, 'a') as f:
                f.write(json.dumps(event) + "\n")

    def get_events(self, limit=100):
        items = []
        with self._lock:
            if not os.path.exists(self.events_path):
                return []
            with open(self.events_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        continue
        return items[-limit:]

