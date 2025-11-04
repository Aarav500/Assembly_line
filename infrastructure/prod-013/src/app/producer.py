import os
import random
import time
from celery import signature

# Ensure app is imported so celery config is loaded
from .celery_app import celery_app  # noqa: F401


def main():
    count = int(os.getenv("PRODUCE_COUNT", "20"))
    min_x = int(os.getenv("PRODUCE_MIN_X", "1"))
    max_x = int(os.getenv("PRODUCE_MAX_X", "100"))

    for i in range(count):
        x = random.randint(min_x, max_x)
        fail_ratio = float(os.getenv("FAIL_RATIO", "0.5"))
        hard_fail_ratio = float(os.getenv("HARD_FAIL_RATIO", "0.1"))

        sig = signature(
            "app.tasks.unreliable_task",
            args=(x,),
            kwargs={"fail_ratio": fail_ratio, "hard_fail_ratio": hard_fail_ratio},
            queue=os.getenv("DEFAULT_QUEUE", "tasks"),
        )
        res = sig.apply_async()
        print(f"Enqueued unreliable_task x={x} task_id={res.id}")
        time.sleep(0.1)


if __name__ == "__main__":
    main()

