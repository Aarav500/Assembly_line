import time
import random


def echo(message: str, delay: float = 0.0):
    if delay and delay > 0:
        time.sleep(delay)
    return {"echo": message}


def unstable(success_rate: float = 0.5):
    if random.random() > success_rate:
        raise RuntimeError("Unstable task simulated failure")
    return {"status": "ok"}


def sleep_task(seconds: float = 1.0):
    time.sleep(seconds)

    return {"slept": seconds}


TASKS = {
    "echo": echo,
    "unstable": unstable,
    "sleep": sleep_task,
}

