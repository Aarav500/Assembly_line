import os
from datetime import timedelta


class Config:
    def __init__(self):
        instance_path = os.path.join(os.getcwd(), "instance")
        os.makedirs(instance_path, exist_ok=True)
        db_path = os.path.join(instance_path, "flaky.db")
        db_uri = f"sqlite:///{db_path}?check_same_thread=False"
        self.SQLALCHEMY_DATABASE_URI = db_uri
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Flakiness analysis parameters
        self.FLAKY_WINDOW_SIZE = int(os.environ.get("FLAKY_WINDOW_SIZE", 20))
        self.FLAKY_MIN_RUNS = int(os.environ.get("FLAKY_MIN_RUNS", 6))
        self.FLAKINESS_THRESHOLD = float(os.environ.get("FLAKINESS_THRESHOLD", 0.35))
        self.RETEST_COOLDOWN_MINUTES = int(os.environ.get("RETEST_COOLDOWN_MINUTES", 60))

        # Scheduler configuration
        self.ANALYZE_INTERVAL_SECONDS = int(os.environ.get("ANALYZE_INTERVAL_SECONDS", 60))
        self.EXECUTE_RETESTS_INTERVAL_SECONDS = int(os.environ.get("EXECUTE_RETESTS_INTERVAL_SECONDS", 30))
        self.AUTO_EXECUTE_RETESTS = os.environ.get("AUTO_EXECUTE_RETESTS", "true").lower() in ["1", "true", "yes"]

        # Misc
        self.JSON_SORT_KEYS = False
        self.TESTING = os.environ.get("TESTING", "false").lower() in ["1", "true", "yes"]

