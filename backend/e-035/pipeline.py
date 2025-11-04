import os
import re
import shutil
import threading
import time
import uuid
from typing import Dict, Any, List

from config import SERVICES, DATA_DIR, WORK_DIR
from storage import Storage
from registry import Registry
from gates import GATE_CLASSES, GateContext


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(WORK_DIR, exist_ok=True)


def parse_dockerfile_base(dockerfile_path: str) -> str:
    try:
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("FROM "):
                    return line.split(" ")[1].strip()
    except FileNotFoundError:
        return ""
    return ""


def compute_channel(tag: str) -> str:
    # e.g., 3.11.8-slim -> 3.11-slim
    # Keep suffix after '-' as is
    if "-" in tag:
        version, suffix = tag.split("-", 1)
        parts = version.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}-{suffix}"
        return f"{version}-{suffix}"
    parts = tag.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return tag


def version_tuple(tag: str) -> List[int]:
    # Extract numeric version like 3.11.8 from tag like 3.11.8-slim
    if "-" in tag:
        v = tag.split("-", 1)[0]
    else:
        v = tag
    nums = []
    for p in v.split("."):
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return nums[:3]


def update_available_for_service(service: Dict[str, Any], current_base: str) -> Dict[str, Any]:
    if not current_base or ":" not in current_base:
        return {"update_available": False}
    image, tag = current_base.split(":", 1)
    channel = compute_channel(tag)
    reg = Registry()
    latest = reg.latest_for_channel(image, channel)
    if not latest:
        return {"update_available": False}
    if version_tuple(latest) > version_tuple(tag):
        return {
            "update_available": True,
            "target_base": f"{image}:{latest}",
            "channel": channel,
            "current_tag": tag,
            "latest_tag": latest,
        }
    return {"update_available": False}


def write_updated_dockerfile(orig_path: str, new_base: str, out_path: str):
    with open(orig_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    replaced = False
    for line in lines:
        if line.strip().startswith("FROM ") and not replaced:
            new_lines.append(f"FROM {new_base}\n")
            replaced = True
        else:
            new_lines.append(line)
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


class PipelineRunner:
    def __init__(self, storage: Storage):
        ensure_dirs()
        self.storage = storage
        self.registry = Registry()
        self._lock = threading.Lock()

    def create_and_start_run(self, service: Dict[str, Any], current_base: str, target_base: str) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        working_dir = os.path.join(WORK_DIR, run_id)
        os.makedirs(working_dir, exist_ok=True)
        run = {
            "id": run_id,
            "service": service,
            "service_name": service["name"],
            "dockerfile": service["dockerfile"],
            "base_current": current_base,
            "base_target": target_base,
            "status": "running",
            "created_at": time.time(),
            "updated_at": time.time(),
            "steps": [],
            "approved": False,
            "working_dir": working_dir,
        }
        self.storage.add_run(run)
        t = threading.Thread(target=self._execute, args=(run_id,), daemon=True)
        t.start()
        return self.storage.get_run(run_id)

    def _execute(self, run_id: str):
        run = self.storage.get_run(run_id)
        if not run:
            return
        service = run["service"]
        dockerfile = service["dockerfile"]
        # Prepare updated Dockerfile
        out_df = os.path.join(run["working_dir"], "Dockerfile.updated")
        write_updated_dockerfile(dockerfile, run["base_target"], out_df)
        # Run gates
        for gate_name in service.get("gates", []):
            gate_cls = GATE_CLASSES[gate_name]
            gate = gate_cls() if callable(gate_cls) else gate_cls
            ctx = GateContext(self.storage.get_run(run_id))
            self.storage.add_step(run_id, gate_name, "running", "")
            result = gate.run(ctx)
            self.storage.update_last_step(run_id, status=result.status, logs=result.message)
            if result.status == "failed":
                self.storage.set_run_status(run_id, "failed")
                return
            if result.status == "waiting":
                self.storage.set_run_status(run_id, "waiting_approval")
                return
        # All gates passed; apply update
        shutil.copyfile(out_df, dockerfile)
        self.storage.set_run_status(run_id, "succeeded")

    def resume_run(self, run_id: str):
        # resume from the next gate after waiting
        run = self.storage.get_run(run_id)
        if not run:
            return
        if run.get("status") != "waiting_approval":
            return
        service = run["service"]
        steps = run.get("steps", [])
        completed_gate_names = [s["name"] for s in steps]
        remaining_gates = [g for g in service.get("gates", []) if g not in completed_gate_names]
        self.storage.set_run_status(run_id, "running")
        # Continue with remaining gates
        for gate_name in remaining_gates:
            gate_cls = GATE_CLASSES[gate_name]
            gate = gate_cls() if callable(gate_cls) else gate_cls
            ctx = GateContext(self.storage.get_run(run_id))
            self.storage.add_step(run_id, gate_name, "running", "")
            result = gate.run(ctx)
            self.storage.update_last_step(run_id, status=result.status, logs=result.message)
            if result.status == "failed":
                self.storage.set_run_status(run_id, "failed")
                return
            if result.status == "waiting":
                self.storage.set_run_status(run_id, "waiting_approval")
                return
        # Apply update if not yet applied
        out_df = os.path.join(run["working_dir"], "Dockerfile.updated")
        dockerfile = run["dockerfile"]
        if os.path.exists(out_df):
            shutil.copyfile(out_df, dockerfile)
        self.storage.set_run_status(run_id, "succeeded")

