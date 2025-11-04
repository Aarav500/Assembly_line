import math
import random
import time
from typing import Any, Dict, Optional

import db
import storage


class TrainingCancelled(Exception):
    pass


def _load_resume_epoch(job_id: str) -> int:
    latest = storage.latest_checkpoint(job_id)
    if not latest:
        return 0
    data = storage.load_checkpoint(latest)
    if not data:
        return 0
    ep = int(data.get("epoch", 0))
    return max(0, ep)


def run_training(job_id: str, params: Dict[str, Any], log_path: str) -> None:
    total_epochs = int(params.get("epochs", 10))
    ckpt_interval = int(params.get("checkpoint_interval", 2))
    # Failure testing knobs
    fail_probability = float(params.get("fail_probability", 0.0))
    fail_on_epoch = params.get("fail_on_epoch")
    fail_on_epoch = int(fail_on_epoch) if fail_on_epoch is not None else None

    start_epoch = _load_resume_epoch(job_id)

    weights = 0.0
    storage.append_log(log_path, f"Job {job_id}: starting training from epoch {start_epoch+1}/{total_epochs}")

    for epoch in range(start_epoch + 1, total_epochs + 1):
        row = db.get_job(job_id)
        if not row:
            storage.append_log(log_path, f"Job {job_id}: missing job row, aborting")
            raise RuntimeError("Job missing")
        status = row.get("status")
        if status == "cancel_requested":
            storage.append_log(log_path, f"Job {job_id}: cancel requested, stopping at epoch {epoch}")
            db.mark_job_canceled(job_id)
            raise TrainingCancelled()

        # Simulate work
        compute = math.sin(epoch) + math.cos(epoch * 0.5)
        weights += compute
        time.sleep(0.4)

        # Update progress
        db.update_progress(job_id, epoch, total_epochs)
        storage.append_log(log_path, f"Job {job_id}: finished epoch {epoch}/{total_epochs}, weights={weights:.4f}")

        # Failure injection for testing
        if fail_on_epoch is not None and epoch == fail_on_epoch:
            raise RuntimeError(f"Injected failure at epoch {epoch}")
        if fail_probability > 0 and random.random() < fail_probability:
            raise RuntimeError("Random failure as per fail_probability")

        # Checkpointing
        if epoch % max(1, ckpt_interval) == 0 or epoch == total_epochs:
            state = {"weights": weights, "meta": {"epoch": epoch}}
            path = storage.save_checkpoint(job_id, epoch, state)
            storage.append_log(log_path, f"Job {job_id}: checkpoint saved at {path}")

    storage.append_log(log_path, f"Job {job_id}: training completed successfully")

