import time
from rq import get_current_job


def add(a: int, b: int) -> int:
    return a + b


def long_task(duration: int = 10):
    job = get_current_job()
    total = max(1, int(duration))
    for i in range(total):
        time.sleep(1)
        if job:
            job.meta["current"] = i + 1
            job.meta["total"] = total
            job.save_meta()
    return {"status": "completed", "total": total}


def heartbeat():
    return {"alive": True, "ts": time.time()}

