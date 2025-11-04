import os

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
BASELINES_DIR = os.path.join(DATA_DIR, "baselines")
RUNS_DIR = os.path.join(DATA_DIR, "runs")


def ensure_dirs():
    for p in [DATA_DIR, BASELINES_DIR, RUNS_DIR]:
        os.makedirs(p, exist_ok=True)

