from typing import Optional, Dict


def set_progress(task, current: int, total: int, message: str = "", extra: Optional[Dict] = None):
    percent = float(current) / float(total) * 100.0 if total else 0.0
    meta = {"current": current, "total": total, "percent": round(percent, 2), "message": message}
    if extra:
        meta.update(extra)
    task.update_state(state="PROGRESS", meta=meta)
    return meta

