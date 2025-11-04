import os
import shutil
import time
from pathlib import Path
from typing import Dict, Any

from ..utils.shell import run as run_cmd


class Actions:
    def __init__(self, config: Dict[str, Any], logger, store, notifier):
        self.config = config
        self.logger = logger
        self.store = store
        self.notifier = notifier
        self.root_dir = Path(__file__).resolve().parents[2]
        self.scripts_dir = self.root_dir / "scripts"

    def notify(self, message: str, title: str = None, severity: str = "info", incident_id: str = None, context: Dict[str, Any] = None):
        self.logger.info({"event": "notify", "title": title, "message": message, "severity": severity})
        self.notifier.notify(title=title or "Runbook Notification", message=message, severity=severity, incident_id=incident_id, extra=context or {})
        return {"notified": True}

    def capture_diagnostics(self, context: Dict[str, Any], service: str = None):
        incident_id = context["incident"]["id"]
        out_dir = self.store.incident_dir(incident_id) / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if service:
            env["SERVICE"] = service
        res = run_cmd([str(self.scripts_dir / "diagnose.sh")], env=env, timeout=self.config.get("shell", {}).get("timeout_seconds", 120))
        diag_file = out_dir / "diagnostics.txt"
        diag_file.write_text(res.get("stdout", "") + "\n" + res.get("stderr", ""), encoding="utf-8")
        return {"artifacts": [str(diag_file)], "returncode": res.get("returncode")}

    def restart_service(self, service: str):
        res = run_cmd([str(self.scripts_dir / "restart_service.sh"), service], timeout=self.config.get("shell", {}).get("timeout_seconds", 120))
        success = res.get("returncode") == 0
        return {"service": service, "success": success, "stdout": res.get("stdout"), "stderr": res.get("stderr")}

    def cleanup_disk(self, mount_point: str = "/", log_dirs=None, journal_vacuum_time: str = None, delete_older_than_days: int = None):
        cfg = self.config.get("defaults", {}).get("cleanup", {})
        log_dirs = log_dirs or cfg.get("log_dirs", ["/var/log"])
        journal_vacuum_time = journal_vacuum_time or cfg.get("journal_vacuum_time", "7d")
        delete_older_than_days = delete_older_than_days or cfg.get("delete_older_than_days", 14)
        args = [str(self.scripts_dir / "cleanup_disk.sh"), mount_point, journal_vacuum_time, str(delete_older_than_days)] + list(log_dirs)
        res = run_cmd(args, timeout=self.config.get("shell", {}).get("timeout_seconds", 600))
        return {"stdout": res.get("stdout"), "stderr": res.get("stderr"), "returncode": res.get("returncode")}

    def run_script(self, path: str, args: str = ""):
        cmd = [path]
        if args:
            cmd += args.split()
        res = run_cmd(cmd, timeout=self.config.get("shell", {}).get("timeout_seconds", 300))
        return {"stdout": res.get("stdout"), "stderr": res.get("stderr"), "returncode": res.get("returncode")}

    def kill_top_cpu_process(self, threshold: float = 95.0):
        cmd = ["bash", "-lc", "ps -eo pid,comm,%cpu --sort=-%cpu | awk 'NR==2{print $1,\"\t\",$2,\"\t\",$3}'"]
        res = run_cmd(cmd)
        out = (res.get("stdout") or "").strip()
        if not out:
            return {"killed": False, "reason": "no_process_found"}
        parts = out.split()
        pid = int(parts[0])
        proc = parts[1]
        cpu = float(parts[2]) if len(parts) > 2 else 0.0
        if cpu < float(threshold):
            return {"killed": False, "pid": pid, "process": proc, "cpu": cpu, "reason": "below_threshold"}
        kill = run_cmd(["bash", "-lc", f"kill -TERM {pid} || true; sleep 2; kill -KILL {pid} || true"])
        return {"killed": True, "pid": pid, "process": proc, "cpu": cpu, "returncode": kill.get("returncode")}

    def identify_top_cpu_processes(self, limit: int = 5):
        cmd = ["bash", "-lc", f"ps -eo pid,comm,%cpu --sort=-%cpu | head -n {limit+1}"]
        res = run_cmd(cmd)
        return {"list": res.get("stdout"), "returncode": res.get("returncode")}

    def vacuum_journal(self, since: str = "7d"):
        res = run_cmd(["bash", "-lc", f"journalctl --vacuum-time={since}"], timeout=self.config.get("shell", {}).get("timeout_seconds", 600))
        return {"stdout": res.get("stdout"), "stderr": res.get("stderr"), "returncode": res.get("returncode")}

    def ping_host(self, host: str, count: int = 3):
        res = run_cmd(["bash", "-lc", f"ping -c {int(count)} {host}"])
        return {"stdout": res.get("stdout"), "stderr": res.get("stderr"), "returncode": res.get("returncode")}

