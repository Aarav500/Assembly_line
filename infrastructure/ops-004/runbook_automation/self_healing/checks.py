import os
import shutil
import time
from pathlib import Path
from typing import Tuple, Dict, Any


class Checks:
    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger

    def _cpu_percent(self, interval: float = 1.0) -> float:
        # Linux /proc/stat based CPU utilization
        def read_cpu_times():
            with open("/proc/stat", "r", encoding="utf-8") as f:
                fields = f.readline().strip().split()[1:]
                vals = list(map(int, fields))
                idle = vals[3]
                total = sum(vals)
                return idle, total
        idle1, total1 = read_cpu_times()
        time.sleep(interval)
        idle2, total2 = read_cpu_times()
        idle = idle2 - idle1
        total = total2 - total1
        usage = 100.0 * (1.0 - (idle / total if total else 0.0))
        return max(0.0, min(100.0, usage))

    def high_cpu(self, threshold: float = None, duration: int = None) -> Tuple[bool, Dict[str, Any]]:
        threshold = float(threshold or self.config.get("defaults", {}).get("cpu_threshold", 85))
        duration = int(duration or self.config.get("defaults", {}).get("cpu_check_duration", 30))
        samples = max(3, min(10, duration))
        interval = max(1.0, duration / samples)
        vals = []
        for _ in range(samples):
            vals.append(self._cpu_percent(interval=max(0.5, interval / 2.0)))
        avg = sum(vals) / len(vals)
        return avg >= threshold, {"average": avg, "samples": vals, "threshold": threshold}

    def disk_full(self, mount_point: str = None, threshold: float = None) -> Tuple[bool, Dict[str, Any]]:
        mount_point = mount_point or self.config.get("defaults", {}).get("disk_mount_point", "/")
        threshold = float(threshold or self.config.get("defaults", {}).get("disk_threshold", 90))
        total, used, free = shutil.disk_usage(mount_point)
        used_pct = used / total * 100.0 if total else 0.0
        return used_pct >= threshold, {"mount_point": mount_point, "used_pct": used_pct, "threshold": threshold, "total": total, "used": used, "free": free}

    def service_down(self, service: str, retries: int = None, delay_seconds: int = None) -> Tuple[bool, Dict[str, Any]]:
        import subprocess
        retries = int(retries or self.config.get("defaults", {}).get("service_check_retries", 2))
        delay_seconds = int(delay_seconds or self.config.get("defaults", {}).get("service_check_delay_seconds", 5))
        status = None
        for attempt in range(retries + 1):
            try:
                proc = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True, timeout=10)
                status = proc.stdout.strip() or proc.stderr.strip()
                if status == "active":
                    return False, {"service": service, "status": status}
            except Exception as e:
                status = str(e)
            if attempt < retries:
                time.sleep(delay_seconds)
        return True, {"service": service, "status": status}

    def low_memory(self, threshold_pct_free: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                meminfo[k.strip()] = int(v.strip().split()[0])  # in kB
        total = meminfo.get("MemTotal", 0)
        available = meminfo.get("MemAvailable", 0)
        free_pct = (available / total * 100.0) if total else 0.0
        return free_pct <= threshold_pct_free, {"total_kb": total, "available_kb": available, "free_pct": free_pct, "threshold": threshold_pct_free}

