import multiprocessing
import os

bind = os.getenv("BIND", "0.0.0.0:8080")
# Use gevent for low-latency IO
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gevent")
workers = int(os.getenv("GUNICORN_WORKERS", str(max(1, multiprocessing.cpu_count() // 2))))
threads = int(os.getenv("GUNICORN_THREADS", "1"))
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "75"))
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"
# Enable TCP reuse for faster handoff across workers
reuse_port = True

