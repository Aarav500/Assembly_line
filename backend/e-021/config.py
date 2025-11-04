import os

class Config:
    def __init__(self):
        self.DESIRED_STATE_PATH = os.getenv("DESIRED_STATE_PATH", "infra/desired_state.yaml")
        self.DRIFT_REPORT_DIR = os.getenv("DRIFT_REPORT_DIR", "data/drift_reports")
        self.DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "file")
        self.GIT_REMOTE = os.getenv("GIT_REMOTE")  # optional
        self.BASE_BRANCH = os.getenv("BASE_BRANCH", "main")
        self.TIMEZONE = os.getenv("TIMEZONE", "UTC")

