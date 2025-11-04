from __future__ import annotations
import os
import socket
from typing import Any, Dict, Callable
from datetime import datetime, timezone

import psutil
import requests


CheckResult = Dict[str, Any]


def _base_result(name: str, type_: str) -> CheckResult:
    return {
        "name": name,
        "type": type_,
        "status": "pass",
        "message": "",
        "metrics": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def check_cpu(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "cpu")
    threshold = float(cfg.get("threshold_percent", 90))
    interval = float(cfg.get("sample_interval", 0.1))
    value = psutil.cpu_percent(interval=interval)
    res["metrics"] = {"cpu_percent": value, "threshold_percent": threshold}
    if value >= threshold:
        res["status"] = "fail"
        res["message"] = f"CPU {value:.1f}% >= {threshold}%"
    else:
        res["message"] = f"CPU {value:.1f}%"
    return res


def check_memory(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "memory")
    threshold = float(cfg.get("threshold_percent", 90))
    vm = psutil.virtual_memory()
    value = vm.percent
    res["metrics"] = {"memory_percent": value, "threshold_percent": threshold}
    if value >= threshold:
        res["status"] = "fail"
        res["message"] = f"Memory {value:.1f}% >= {threshold}%"
    else:
        res["message"] = f"Memory {value:.1f}%"
    return res


def check_disk(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "disk")
    path = cfg.get("path", "/")
    min_free = float(cfg.get("min_free_percent", 10))
    usage = psutil.disk_usage(path)
    free_percent = 100.0 - usage.percent
    res["metrics"] = {
        "path": path,
        "free_percent": free_percent,
        "min_free_percent": min_free,
        "used_percent": usage.percent,
    }
    if free_percent <= min_free:
        res["status"] = "fail"
        res["message"] = f"Disk free {free_percent:.1f}% <= {min_free}% on {path}"
    else:
        res["message"] = f"Disk free {free_percent:.1f}% on {path}"
    return res


def check_http(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "http")
    url = cfg["url"]
    timeout = float(cfg.get("timeout_seconds", 2))
    expected = int(cfg.get("expected_status", 200))
    try:
        r = requests.get(url, timeout=timeout)
        res["metrics"] = {"status_code": r.status_code, "expected": expected}
        if r.status_code != expected:
            res["status"] = "fail"
            res["message"] = f"HTTP {url} returned {r.status_code}, expected {expected}"
        else:
            res["message"] = f"HTTP {url} OK"
    except requests.RequestException as e:
        res["status"] = "fail"
        res["message"] = f"HTTP error: {e}"
    return res


def check_tcp(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "tcp")
    host = cfg["host"]
    port = int(cfg["port"])
    timeout = float(cfg.get("timeout_seconds", 2))
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        res["message"] = f"TCP {host}:{port} reachable"
    except OSError as e:
        res["status"] = "fail"
        res["message"] = f"TCP connect failed {host}:{port} - {e}"
    res["metrics"] = {"host": host, "port": port}
    return res


def check_process(name: str, cfg: Dict[str, Any]) -> CheckResult:
    res = _base_result(name, "process")
    proc_name = cfg.get("process_name")
    min_count = int(cfg.get("min_count", 1))
    match_case = bool(cfg.get("match_case", False))
    if not proc_name:
        res["status"] = "fail"
        res["message"] = "process_name not provided"
        return res
    count = 0
    for p in psutil.process_iter(["name"]):
        try:
            name_val = p.info.get("name") or ""
            if not match_case:
                if name_val.lower() == proc_name.lower():
                    count += 1
            else:
                if name_val == proc_name:
                    count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    res["metrics"] = {"process_name": proc_name, "count": count, "min_count": min_count}
    if count < min_count:
        res["status"] = "fail"
        res["message"] = f"Process '{proc_name}' count {count} < {min_count}"
    else:
        res["message"] = f"Process '{proc_name}' count {count}"
    return res


def check_command(name: str, cfg: Dict[str, Any]) -> CheckResult:
    import subprocess
    res = _base_result(name, "command")
    cmd = cfg.get("command")
    timeout = float(cfg.get("timeout_seconds", 5))
    if not cmd:
        res["status"] = "fail"
        res["message"] = "command not provided"
        return res
    try:
        cp = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout, text=True)
        res["metrics"] = {"returncode": cp.returncode}
        if cp.returncode != 0:
            res["status"] = "fail"
            res["message"] = f"Command failed rc={cp.returncode}: {cp.stderr.strip() or cp.stdout.strip()}"
        else:
            res["message"] = f"Command succeeded: {cmd}"
    except Exception as e:
        res["status"] = "fail"
        res["message"] = f"Command error: {e}"
    return res


CHECK_HANDLERS: Dict[str, Callable[[str, Dict[str, Any]], CheckResult]] = {
    "cpu": check_cpu,
    "memory": check_memory,
    "disk": check_disk,
    "http": check_http,
    "tcp": check_tcp,
    "process": check_process,
    "command": check_command,
}


def run_check(name: str, cfg: Dict[str, Any]) -> CheckResult:
    type_ = cfg.get("type")
    if not type_:
        r = _base_result(name, "unknown")
        r["status"] = "fail"
        r["message"] = "Missing 'type' in check config"
        return r
    handler = CHECK_HANDLERS.get(type_)
    if not handler:
        r = _base_result(name, type_)
        r["status"] = "fail"
        r["message"] = f"Unknown check type: {type_}"
        return r
    return handler(name, cfg)

