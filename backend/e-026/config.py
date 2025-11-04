import json
import os
from typing import Any, Dict


class AppConfig:
    def __init__(self) -> None:
        self.ENV = os.getenv("FLASK_ENV", "production")
        self.DEBUG = self.ENV == "development"
        self.DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
        self.INGESTED_FILE = os.path.join(self.DATA_DIR, "ingested.json")
        self.CONFIG_FILE = os.path.join(self.DATA_DIR, "config.json")

        defaults = {
            "savings_alert_threshold": 50.0,  # USD/month
            "high_savings_threshold": 200.0,  # USD/month
            "idle_hours_threshold": 140,      # in last 7 days
        }
        file_cfg: Dict[str, Any] = {}
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
        except Exception:
            file_cfg = {}

        self.SAVINGS_ALERT_THRESHOLD = float(os.getenv("SAVINGS_ALERT_THRESHOLD", file_cfg.get("savings_alert_threshold", defaults["savings_alert_threshold"])))
        self.HIGH_SAVINGS_THRESHOLD = float(os.getenv("HIGH_SAVINGS_THRESHOLD", file_cfg.get("high_savings_threshold", defaults["high_savings_threshold"])))
        self.IDLE_HOURS_THRESHOLD = int(os.getenv("IDLE_HOURS_THRESHOLD", file_cfg.get("idle_hours_threshold", defaults["idle_hours_threshold"])))

    def to_dict(self):
        return {
            "savings_alert_threshold": self.SAVINGS_ALERT_THRESHOLD,
            "high_savings_threshold": self.HIGH_SAVINGS_THRESHOLD,
            "idle_hours_threshold": self.IDLE_HOURS_THRESHOLD,
        }

