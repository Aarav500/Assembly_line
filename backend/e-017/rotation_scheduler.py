import threading
import time
import uuid
from typing import Dict, List, Optional


class RotationScheduler:
    def __init__(self, vault_manager, check_interval: float = 1.0):
        self.vault = vault_manager
        self.check_interval = check_interval
        self._jobs: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="RotationScheduler", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def load_jobs(self, jobs: List[Dict]):
        for job in jobs:
            self.add_job(job)

    def add_job(self, job: Dict) -> str:
        # job fields: type, interval_seconds, and type-specific config
        jtype = job.get("type")
        interval = job.get("interval_seconds")
        if not jtype or not isinstance(interval, (int, float)):
            raise ValueError("Job must include 'type' and numeric 'interval_seconds'")
        jid = job.get("id") or str(uuid.uuid4())
        now = time.time()
        with self._lock:
            self._jobs[jid] = {
                **job,
                "id": jid,
                "last_run": None,
                "next_run": now + float(interval),
                "errors": 0,
            }
        return jid

    def describe_jobs(self) -> List[Dict]:
        with self._lock:
            return list(self._jobs.values())

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(self.check_interval)

    def _tick(self):
        now = time.time()
        due: List[str] = []
        with self._lock:
            for jid, job in self._jobs.items():
                if now >= job.get("next_run", 0):
                    due.append(jid)
        for jid in due:
            self._run_job(jid)

    def _run_job(self, jid: str):
        with self._lock:
            job = dict(self._jobs.get(jid, {}))
        if not job:
            return
        jtype = job.get("type")
        try:
            if jtype == "kv_random":
                self._run_kv_random(job)
            elif jtype == "database_root":
                self._run_database_root(job)
            else:
                raise ValueError(f"Unknown job type: {jtype}")
            self._update_post_run(jid, success=True)
        except Exception:
            self._update_post_run(jid, success=False)

    def _update_post_run(self, jid: str, success: bool):
        with self._lock:
            job = self._jobs.get(jid)
            if not job:
                return
            job["last_run"] = time.time()
            if success:
                job["errors"] = 0
            else:
                job["errors"] = job.get("errors", 0) + 1
            job["next_run"] = job["last_run"] + float(job.get("interval_seconds", 60))

    def _run_kv_random(self, job: Dict):
        mount = job.get("mount", "secret")
        path = job.get("path")
        field = job.get("field", "password")
        length = int(job.get("length", 32))
        alphabet = job.get("alphabet")
        preserve_fields = job.get("preserve_fields", {})
        if not path:
            raise ValueError("kv_random job requires 'path'")
        self.vault.rotate_kv_random_secret(
            path=path,
            field=field,
            length=length,
            mount_point=mount,
            alphabet=alphabet,
            preserve_fields=preserve_fields,
        )

    def _run_database_root(self, job: Dict):
        mount = job.get("mount", "database")
        connection = job.get("connection")
        if not connection:
            raise ValueError("database_root job requires 'connection'")
        self.vault.rotate_database_root(mount_point=mount, connection_name=connection)

