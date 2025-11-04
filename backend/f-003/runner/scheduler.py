from __future__ import annotations
import threading
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from .config import Config, FlowConfig
from .flows import FlowRunner


class SchedulerManager:
    def __init__(self, runner: FlowRunner):
        self.scheduler = BackgroundScheduler()
        self.runner = runner
        self._config: Optional[Config] = None
        self._lock = threading.Lock()

    def start(self):
        self.scheduler.start()

    def shutdown(self):
        self.scheduler.shutdown(wait=False)

    def get_config(self) -> Optional[Config]:
        return self._config

    def reschedule_all(self, config: Config):
        with self._lock:
            # Remove previous jobs
            for job in list(self.scheduler.get_jobs()):
                self.scheduler.remove_job(job.id)
            # Set new config
            self._config = config
            self.runner.set_config(config)
            # Schedule enabled flows
            for flow in config.flows:
                if not flow.enabled:
                    continue
                self.scheduler.add_job(
                    func=self._run_job,
                    args=[flow.id],
                    id=f"flow:{flow.id}",
                    replace_existing=True,
                    trigger=IntervalTrigger(seconds=flow.schedule_every_sec)
                )

    def run_now(self, flow_id: str) -> bool:
        cfg = self._config
        if not cfg:
            return False
        f = self._get_flow(cfg, flow_id)
        if not f or not f.enabled:
            return False
        self.scheduler.add_job(func=self._run_job, args=[flow_id])
        return True

    def _get_flow(self, cfg: Config, flow_id: str) -> Optional[FlowConfig]:
        for f in cfg.flows:
            if f.id == flow_id:
                return f
        return None

    def _run_job(self, flow_id: str):
        try:
            self.runner.run_and_record(flow_id)
        except Exception as e:
            # Avoid scheduler crash
            print(f"Error executing flow {flow_id}: {e}")

