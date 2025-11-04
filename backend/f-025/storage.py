import os
import json
from typing import Dict, List, Optional
from config import DATA_DIR, BASELINES_DIR, RUNS_DIR, ensure_dirs


def ensure_storage():
    ensure_dirs()


def _save_json(path: str, obj: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Baseline storage

def _baseline_path(baseline_id: str) -> str:
    return os.path.join(BASELINES_DIR, f"{baseline_id}.json")


def save_baseline(baseline: dict):
    ensure_dirs()
    path = _baseline_path(baseline["id"])
    _save_json(path, baseline)


def load_baseline(baseline_id: str) -> Optional[dict]:
    return _load_json(_baseline_path(baseline_id))


def list_baselines() -> List[dict]:
    ensure_dirs()
    items = []
    for name in os.listdir(BASELINES_DIR):
        if not name.endswith(".json"):
            continue
        obj = _load_json(os.path.join(BASELINES_DIR, name))
        if obj:
            items.append(obj)
    # newest first by created_at if available
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


# Run storage

def _run_path(run_id: str) -> str:
    return os.path.join(RUNS_DIR, f"{run_id}.json")


def save_run(run: dict):
    ensure_dirs()
    _save_json(_run_path(run["id"]), run)


def load_run(run_id: str) -> Optional[dict]:
    return _load_json(_run_path(run_id))


def list_runs() -> List[dict]:
    ensure_dirs()
    items = []
    for name in os.listdir(RUNS_DIR):
        if not name.endswith(".json"):
            continue
        obj = _load_json(os.path.join(RUNS_DIR, name))
        if obj:
            items.append(obj)
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def runs_for_baseline(baseline_id: str) -> List[dict]:
    return [r for r in list_runs() if r.get("baseline_id") == baseline_id]

