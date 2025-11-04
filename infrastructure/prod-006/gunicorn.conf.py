import multiprocessing
import os

bind = os.environ.get("BIND", "0.0.0.0:8000")
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count()))
threads = int(os.environ.get("WEB_THREADS", "2"))
timeout = int(os.environ.get("WEB_TIMEOUT", "30"))
worker_class = os.environ.get("WORKER_CLASS", "gthread")
loglevel = os.environ.get("LOG_LEVEL", "info")
graceful_timeout = int(os.environ.get("GRACEFUL_TIMEOUT", "30"))
accesslog = "-"
errorlog = "-"

# Preload app can reduce startup time; beware with forking and threads
preload_app = os.environ.get("PRELOAD_APP", "false").lower() in ("1", "true", "yes", "on")

# Ensure Python buffered output is disabled (optional, for logging immediacy)
os.environ.setdefault("PYTHONUNBUFFERED", "1")

