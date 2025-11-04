STORAGE_FILE = "data/db.json"

DEFAULT_POLICY = {
    "heavy_threshold": 60.0,
    "weights": {
        "heavy": {"cost": 0.6, "speed": 0.25, "queue": 0.1, "risk": 0.05},
        "normal": {"cost": 0.35, "speed": 0.45, "queue": 0.15, "risk": 0.05},
        "latency_sensitive": {"cost": 0.15, "speed": 0.7, "queue": 0.1, "risk": 0.05},
    },
    "constraints": {
        "max_queue_minutes_for_high_priority": 5.0
    }
}

