import os
import json
from typing import Any, Dict, Optional, List, Tuple
from pathlib import Path

import config


def ensure_job_dirs(job_id: str) -> Tuple[str, str]:
    chk_dir = Path(config.CHECKPOINT_DIR) / job_id
    log_dir = Path(config.LOG_DIR)
    chk_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = str(log_dir / f"{job_id}.log")
    return str(chk_dir), log_path


def checkpoint_path(job_id: str, epoch: int) -> str:
    return str(Path(config.CHECKPOINT_DIR) / job_id / f"epoch-{epoch}.json")


def latest_checkpoint(job_id: str) -> Optional[str]:
    dir_path = Path(config.CHECKPOINT_DIR) / job_id
    if not dir_path.exists():
        return None
    files = sorted(dir_path.glob("epoch-*.json"))
    if not files:
        return None
    return str(files[-1])


def save_checkpoint(job_id: str, epoch: int, state: Dict[str, Any]) -> str:
    path = checkpoint_path(job_id, epoch)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"epoch": epoch, "state": state}, f)
    return path


def load_checkpoint(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_checkpoints(job_id: str) -> List[Dict[str, Any]]:
    dir_path = Path(config.CHECKPOINT_DIR) / job_id
    if not dir_path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for p in sorted(dir_path.glob("epoch-*.json")):
        try:
            epoch_part = p.stem.split("-")[-1]
            ep = int(epoch_part)
        except Exception:
            ep = None
        items.append({"path": str(p), "epoch": ep})
    return items


def append_log(log_path: str, message: str) -> None:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message.rstrip("\n") + "\n")


def read_log(log_path: str, max_bytes: int = 200_000) -> str:
    if not os.path.exists(log_path):
        return ""
    size = os.path.getsize(log_path)
    with open(log_path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""

