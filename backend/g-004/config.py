import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUITES_DIR = os.environ.get("SUITES_DIR", os.path.join(BASE_DIR, "suites"))
RUNS_DIR = os.environ.get("RUNS_DIR", os.path.join(BASE_DIR, "runs"))

# HTTP model defaults
HTTP_TIMEOUT = float(os.environ.get("HTTP_MODEL_TIMEOUT", "30"))

