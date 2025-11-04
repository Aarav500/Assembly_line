import os
import random
import tempfile
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler


class SchedulerService:
    def __init__(self, backup, retention, storage, drill_cfg: dict, backup_cfg: dict, retention_cfg: dict):
        self.backup = backup
        self.retention = retention
        self.storage = storage
        self.drill_cfg = drill_cfg or {}
        self.backup_cfg = backup_cfg or {}
        self.retention_cfg = retention_cfg or {}
        self.scheduler = BackgroundScheduler()
        self.started = False

    def start(self):
        if self.started:
            return
        # Schedule backup
        bi = int(self.backup_cfg.get("schedule_interval_seconds", 0) or 0)
        if bi > 0:
            self.scheduler.add_job(self._job_backup, "interval", seconds=bi, id="backup_job", replace_existing=True)
        # Schedule retention
        ri = int(self.retention_cfg.get("schedule_interval_seconds", 0) or 0)
        if ri > 0:
            self.scheduler.add_job(self._job_retention, "interval", seconds=ri, id="retention_job", replace_existing=True)
        # Schedule drill
        if bool(self.drill_cfg.get("enabled", True)):
            di = int(self.drill_cfg.get("schedule_interval_seconds", 0) or 0)
            if di > 0:
                self.scheduler.add_job(self._job_drill, "interval", seconds=di, id="drill_job", replace_existing=True)
        self.scheduler.start()
        self.started = True

    def shutdown(self):
        if self.started:
            try:
                self.scheduler.shutdown(wait=False)
            except Exception:
                pass
            self.started = False

    def _job_backup(self):
        try:
            self.backup.create_backup(reason="scheduled")
        except Exception as e:
            # Log to a file under storage base
            self._log_event("backup_job_error", {"error": str(e)})

    def _job_retention(self):
        try:
            self.retention.apply()
        except Exception as e:
            self._log_event("retention_job_error", {"error": str(e)})

    def _job_drill(self):
        try:
            self.run_drill_now()
        except Exception as e:
            self._log_event("drill_job_error", {"error": str(e)})

    def run_drill_now(self, backup_id: str | None = None) -> dict:
        items = self.storage.list_backups()
        if not items:
            result = {
                "status": "skipped",
                "reason": "no_backups",
                "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self.storage.record_drill_result(result)
            return result

        chosen = None
        if backup_id:
            for it in items:
                if it.get("id") == backup_id:
                    chosen = it
                    break
        if not chosen:
            chosen = random.choice(items)

        tmp_dir = tempfile.mkdtemp(prefix="drill_restore_")
        ok = True
        error = None
        try:
            from .restore_service import RestoreService
            rest = RestoreService(self.storage)
            rest.restore_backup(chosen["id"], tmp_dir, verify_checksum=True)
        except Exception as e:
            ok = False
            error = str(e)
        finally:
            # Clean up temp directory contents
            try:
                for root, dirs, files in os.walk(tmp_dir, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except Exception:
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except Exception:
                            pass
                os.rmdir(tmp_dir)
            except Exception:
                pass

        result = {
            "status": "success" if ok else "failed",
            "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "backup_id": chosen["id"],
            "error": error,
        }
        self.storage.record_drill_result(result)
        return result

    def _log_event(self, name: str, payload: dict):
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = os.path.join(self.storage.base_path, f"{name}_{ts}.log")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(str(payload) + "\n")
        except Exception:
            pass

