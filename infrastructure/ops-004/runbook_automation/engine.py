import json
import time
from pathlib import Path
from typing import Dict, Any, List

import yaml
from jinja2 import Environment, BaseLoader


class RunbookEngine:
    def __init__(self, config: Dict[str, Any], runbook_dir: Path, store, notifier, logger, actions, checks):
        self.config = config
        self.runbook_dir = Path(runbook_dir)
        self.store = store
        self.notifier = notifier
        self.logger = logger
        self.actions = actions
        self.checks = checks
        self.env = Environment(loader=BaseLoader())
        self._runbooks_cache = None

    def load_runbooks(self) -> List[Dict[str, Any]]:
        if self._runbooks_cache is not None:
            return self._runbooks_cache
        runbooks = []
        for f in self.runbook_dir.glob("*.yml"):
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
                if data:
                    data["__path__"] = str(f)
                    runbooks.append(data)
        self._runbooks_cache = runbooks
        return runbooks

    def list_runbooks(self):
        return [
            {
                "id": rb.get("id"),
                "name": rb.get("name"),
                "description": rb.get("description"),
            }
            for rb in self.load_runbooks()
        ]

    def _find_runbook(self, incident_id: str) -> Dict[str, Any]:
        for rb in self.load_runbooks():
            if rb.get("id") == incident_id:
                return rb
        raise ValueError(f"Runbook not found: {incident_id}")

    def _eval_when(self, expr: str, ctx: Dict[str, Any]) -> bool:
        try:
            compiled = self.env.compile_expression(expr)
            val = compiled(**ctx)
            return bool(val)
        except Exception:
            # fallback: render as text and check for truthy
            txt = self.env.from_string(expr).render(**ctx)
            truthy = str(txt).strip().lower() in ("1", "true", "yes", "on")
            return truthy

    def run(self, incident_id: str, context: Dict[str, Any] = None, dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
        runbook = self._find_runbook(incident_id)
        ctx = {
            "config": self.config,
            "incident": {
                "id": None,
                "type": runbook.get("id"),
                "name": runbook.get("name"),
                "self_heal": bool(runbook.get("self_heal", True)),
                "started_at": time.time(),
            },
            "context": context or {},
            "results": {},
        }

        incident_record = self.store.create_incident(runbook, ctx["context"], dry_run=dry_run)
        ctx["incident"]["id"] = incident_record["id"]

        self.logger.info({"event": "runbook_start", "runbook": runbook.get("id"), "incident_id": ctx["incident"]["id"], "dry_run": dry_run})
        self.notifier.notify(
            title=f"Runbook started: {runbook.get('name')}",
            message=f"Incident {ctx['incident']['id']} started for {runbook.get('id')}",
            severity="info",
            incident_id=ctx["incident"]["id"],
            extra={"context": ctx["context"]},
        )

        # Trigger check
        triggered = True
        trigger = runbook.get("trigger")
        trigger_data = {}
        if trigger and not force:
            check_name = trigger.get("check")
            params = trigger.get("params", {})
            if not hasattr(self.checks, check_name):
                raise ValueError(f"Unknown check: {check_name}")
            triggered, trigger_data = getattr(self.checks, check_name)(**self._render_params(params, ctx))
            ctx["results"]["trigger"] = {"triggered": triggered, "data": trigger_data}
            self.store.append_step(ctx["incident"]["id"], "trigger_check", {"check": check_name, "params": params, "result": ctx["results"]["trigger"]})

        if not triggered and not force:
            self.logger.info({"event": "runbook_skipped", "reason": "trigger_not_met", "incident_id": ctx["incident"]["id"]})
            self.store.finalize_incident(ctx["incident"]["id"], status="skipped", summary="Trigger not met")
            self.notifier.notify(
                title=f"Runbook skipped: {runbook.get('name')}",
                message=f"Trigger not met for incident {ctx['incident']['id']}",
                severity="info",
                incident_id=ctx["incident"]["id"],
            )
            return {"status": "skipped", "reason": "trigger_not_met", "incident_id": ctx["incident"]["id"]}

        # Execute steps
        steps = runbook.get("steps", [])
        for idx, step in enumerate(steps, start=1):
            action_name = step.get("action")
            when_expr = step.get("when")
            params = step.get("params", {})

            if when_expr:
                ok = self._eval_when(when_expr, ctx)
                if not ok:
                    self.store.append_step(ctx["incident"]["id"], f"step_{idx}", {"action": action_name, "skipped": True, "reason": "when_false"})
                    continue

            if not hasattr(self.actions, action_name):
                raise ValueError(f"Unknown action: {action_name}")

            rendered_params = self._render_params(params, ctx)

            if dry_run:
                res = {"dry_run": True, "action": action_name, "params": rendered_params}
            else:
                try:
                    res = getattr(self.actions, action_name)(context=ctx, **rendered_params)
                except TypeError:
                    res = getattr(self.actions, action_name)(**rendered_params)

            ctx["results"][action_name] = res
            self.store.append_step(ctx["incident"]["id"], f"step_{idx}", {"action": action_name, "params": rendered_params, "result": res})

        # Finalize
        status = "completed"
        summary = runbook.get("success_message", f"Runbook {runbook.get('id')} completed")
        self.store.finalize_incident(ctx["incident"]["id"], status=status, summary=summary, context=ctx)

        self.notifier.notify(
            title=f"Runbook completed: {runbook.get('name')}",
            message=f"Incident {ctx['incident']['id']} completed",
            severity="good",
            incident_id=ctx["incident"]["id"],
        )

        return {"status": status, "incident_id": ctx["incident"]["id"], "summary": summary}

    def _render_params(self, params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        rendered = {}
        for k, v in (params or {}).items():
            if isinstance(v, str):
                rendered[k] = self.env.from_string(v).render(**ctx)
            else:
                rendered[k] = v
        return rendered

