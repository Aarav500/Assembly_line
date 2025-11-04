import json
import os
import time
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader


class IncidentStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir = Path(__file__).resolve().parents[1] / "templates"
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))

    def _new_id(self) -> str:
        return time.strftime("%Y%m%d-%H%M%S")

    def incident_dir(self, incident_id: str) -> Path:
        return self.base_dir / incident_id

    def create_incident(self, runbook: Dict[str, Any], context: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        inc_id = self._new_id()
        inc_dir = self.incident_dir(inc_id)
        inc_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "id": inc_id,
            "runbook": {k: runbook.get(k) for k in ("id", "name", "description")},
            "context": context,
            "dry_run": dry_run,
            "created_at": time.time(),
            "status": "running",
            "steps": [],
        }
        (inc_dir / "incident.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta

    def append_step(self, incident_id: str, step_name: str, data: Dict[str, Any]):
        inc_dir = self.incident_dir(incident_id)
        meta_path = inc_dir / "incident.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        entry = {"time": time.time(), "step": step_name, "data": data}
        meta.setdefault("steps", []).append(entry)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log_path = inc_dir / "steps.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def finalize_incident(self, incident_id: str, status: str, summary: str, context: Dict[str, Any] = None):
        inc_dir = self.incident_dir(incident_id)
        meta_path = inc_dir / "incident.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["status"] = status
        meta["summary"] = summary
        meta["finished_at"] = time.time()
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        # Render report
        tmpl = self.env.get_template("incident_report.md.j2")
        report = tmpl.render(meta=meta, context=context or {})
        (inc_dir / "report.md").write_text(report, encoding="utf-8")

