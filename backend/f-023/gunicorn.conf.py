import multiprocessing
import os

bind = os.getenv("BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count()))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
preload_app = True

# Graceful timeouts
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

