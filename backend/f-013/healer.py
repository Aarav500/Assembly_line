from __future__ import annotations
import fnmatch
import os
import shutil
import subprocess
import time
from typing import Any, Dict, List
import psutil


def _respect_dry_run(dry_run: bool, action_desc: str) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry_run", "message": f"Would perform: {action_desc}"}
    return {}


def restart_command(check_name: str, check_cfg: Dict[str, Any], params: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    cmd = (params or {}).get("command") or check_cfg.get("heal_params", {}).get("command")
    if not cmd:
        return {"status": "error", "message": "No command provided for restart_command"}
    pre = _respect_dry_run(dry_run, f"run command: {cmd}")
    if pre:
        return pre
    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        if cp.returncode == 0:
            return {"status": "ok", "message": f"Command executed: {cmd}"}
        return {"status": "error", "message": f"Command failed rc={cp.returncode}: {cp.stderr.strip() or cp.stdout.strip()}"}
    except Exception as e:
        return {"status": "error", "message": f"Command error: {e}"}


def kill_high_cpu_processes(check_name: str, check_cfg: Dict[str, Any], params: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    min_cpu = float((params or {}).get("min_cpu_percent", check_cfg.get("heal_params", {}).get("min_cpu_percent", 50)))
    max_kill = int((params or {}).get("max_processes_to_kill", check_cfg.get("heal_params", {}).get("max_processes_to_kill", 1)))
    # sample CPU once to get recent values
    for p in psutil.process_iter():
        try:
            p.cpu_percent(None)
        except Exception:
            pass
    time.sleep(0.2)
    offenders = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            cpu = p.cpu_percent(None)
            if cpu >= min_cpu and p.pid != os.getpid():
                offenders.append((cpu, p))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    offenders.sort(key=lambda x: x[0], reverse=True)
    killed: List[int] = []
    msgs: List[str] = []
    for cpu, proc in offenders[:max_kill]:
        desc = f"kill pid={proc.pid} name={proc.info.get('name')} cpu={cpu:.1f}%"
        pre = _respect_dry_run(dry_run, desc)
        if pre:
            msgs.append(pre["message"])  # type: ignore
            continue
        try:
            proc.kill()
            killed.append(proc.pid)
            msgs.append(f"{desc} - OK")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            msgs.append(f"{desc} - ERROR: {e}")
    if not offenders:
        return {"status": "noop", "message": "No high-CPU offenders found"}
    status = "ok" if killed or dry_run else "error"
    return {"status": status, "message": "; ".join(msgs)}


def kill_high_memory_processes(check_name: str, check_cfg: Dict[str, Any], params: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    min_mem = float((params or {}).get("min_memory_percent", check_cfg.get("heal_params", {}).get("min_memory_percent", 50)))
    max_kill = int((params or {}).get("max_processes_to_kill", check_cfg.get("heal_params", {}).get("max_processes_to_kill", 1)))
    offenders = []
    for p in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            mem = p.info.get("memory_percent") or p.memory_percent()
            if mem >= min_mem and p.pid != os.getpid():
                offenders.append((mem, p))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    offenders.sort(key=lambda x: x[0], reverse=True)
    killed = []
    msgs = []
    for mem, proc in offenders[:max_kill]:
        desc = f"kill pid={proc.pid} name={proc.info.get('name')} mem={mem:.1f}%"
        pre = _respect_dry_run(dry_run, desc)
        if pre:
            msgs.append(pre["message"])  # type: ignore
            continue
        try:
            proc.kill()
            killed.append(proc.pid)
            msgs.append(f"{desc} - OK")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            msgs.append(f"{desc} - ERROR: {e}")
    if not offenders:
        return {"status": "noop", "message": "No high-memory offenders found"}
    status = "ok" if killed or dry_run else "error"
    return {"status": status, "message": "; ".join(msgs)}


def _remove_path(path: str) -> tuple[bool, str]:
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
        return True, f"removed {path}"
    except Exception as e:
        return False, f"failed {path}: {e}"


def free_disk_space(check_name: str, check_cfg: Dict[str, Any], params: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    targets = (params or {}).get("targets") or check_cfg.get("heal_params", {}).get("targets", [])
    now = time.time()
    removed = 0
    attempted = 0
    msgs: List[str] = []
    for target in targets:
        base = target.get("path")
        patterns = target.get("patterns", ["*"])
        max_age_hours = float(target.get("max_age_hours", 24))
        max_age_secs = max_age_hours * 3600
        if not base or not os.path.exists(base):
            msgs.append(f"skip missing {base}")
            continue
        for root, dirs, files in os.walk(base):
            candidates = [os.path.join(root, f) for f in files] + [os.path.join(root, d) for d in dirs]
            for p in candidates:
                try:
                    mtime = os.path.getmtime(p)
                except Exception:
                    continue
                age = now - mtime
                if age < max_age_secs:
                    continue
                if not any(fnmatch.fnmatch(os.path.basename(p), pat) for pat in patterns):
                    continue
                attempted += 1
                pre = _respect_dry_run(dry_run, f"remove {p}")
                if pre:
                    msgs.append(pre["message"])  # type: ignore
                    continue
                ok, m = _remove_path(p)
                if ok:
                    removed += 1
                msgs.append(m)
    status = "ok" if (removed > 0 or dry_run) else "noop"
    return {"status": status, "message": f"removed={removed} attempted={attempted}; " + "; ".join(msgs[:10])}


HEAL_ACTIONS = {
    "restart_command": restart_command,
    "kill_high_cpu_processes": kill_high_cpu_processes,
    "kill_high_memory_processes": kill_high_memory_processes,
    "free_disk_space": free_disk_space,
}


def run_heal(action_name: str, check_name: str, check_cfg: Dict[str, Any], params: Dict[str, Any] | None, dry_run: bool = False) -> Dict[str, Any]:
    fn = HEAL_ACTIONS.get(action_name)
    if not fn:
        return {"status": "error", "message": f"Unknown heal action: {action_name}"}
    return fn(check_name, check_cfg, params or {}, dry_run=dry_run)

