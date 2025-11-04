import config


def desired_workers(pending_jobs: int, queued_jobs: int, running_jobs: int) -> int:
    backlog = pending_jobs + queued_jobs
    if backlog <= 0:
        return max(config.MIN_WORKERS, 0)
    target = min(config.MAX_WORKERS, max(config.MIN_WORKERS, backlog))
    return target

