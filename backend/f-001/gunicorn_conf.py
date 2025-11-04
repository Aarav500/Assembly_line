import os

# Example Gunicorn config to work with Prometheus multiprocess metrics
# Usage: set env PROMETHEUS_MULTIPROC_DIR to a writable directory

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))


def child_exit(server, worker):
    try:
        from prometheus_client import multiprocess
        multiprocess.mark_process_dead(worker.pid)
    except Exception:  # noqa: S110
        pass

