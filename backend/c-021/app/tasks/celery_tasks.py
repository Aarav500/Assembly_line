import time
from app.celery_app import celery


@celery.task(bind=True)
def add(self, a: int, b: int) -> int:
    return a + b


@celery.task(bind=True)
def long_task(self, duration: int = 10):
    total = max(1, int(duration))
    for i in range(total):
        time.sleep(1)
        self.update_state(state="PROGRESS", meta={"current": i + 1, "total": total})
    return {"status": "completed", "total": total}


@celery.task(bind=True)
def heartbeat(self):
    # Lightweight periodic task to prove scheduler works
    return {"alive": True, "ts": time.time()}

