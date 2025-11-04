from __future__ import annotations
import time
import json
from typing import Dict, Any, List, Optional
import requests

from .config import Config, FlowConfig, StepConfig, CheckConfig
from .storage import Storage
from .alerting import AlertManager
from .utils import evaluate_checks


class FlowRunner:
    def __init__(self, storage: Storage, alert_manager: AlertManager, config: Config):
        self.storage = storage
        self.alert_manager = alert_manager
        self._config = config

    def set_config(self, cfg: Config):
        self._config = cfg

    def get_flow(self, flow_id: str) -> Optional[FlowConfig]:
        for f in self._config.flows:
            if f.id == flow_id:
                return f
        return None

    def run_and_record(self, flow_id: str) -> Optional[Dict[str, Any]]:
        flow = self.get_flow(flow_id)
        if not flow or not flow.enabled:
            return None
        attempts = flow.retry_on_failure + 1
        last_result = None
        for attempt in range(1, attempts + 1):
            result = self._run_flow(flow)
            last_result = result
            if result["success"]:
                break
            if attempt < attempts:
                time.sleep(flow.retry_delay_seconds)
        # Alerting and persistence already handled in _run_flow
        return last_result

    def _run_flow(self, flow: FlowConfig) -> Dict[str, Any]:
        started_at = time.time()
        step_results: List[Dict[str, Any]] = []
        success = True
        error_summary = None

        timeout_default = self._config.app.default_timeout_seconds
        verify_ssl = self._config.app.verify_ssl

        session = requests.Session()

        for step in flow.steps:
            step_start = time.time()
            try:
                method = step.method.upper()
                req_kwargs = {
                    "headers": step.headers or {},
                    "params": step.params or {},
                    "timeout": step.timeout_sec or timeout_default,
                    "verify": verify_ssl,
                }
                if step.json is not None:
                    req_kwargs["json"] = step.json
                elif step.data is not None:
                    req_kwargs["data"] = step.data

                resp = session.request(method, step.url, **req_kwargs)
                elapsed_ms = (time.time() - step_start) * 1000.0
                body_excerpt = None
                try:
                    # attempt to preserve json-ability for checks
                    body_text = resp.text if resp.text is not None else ""
                    body_excerpt = body_text[:512]
                except Exception:
                    body_excerpt = "<non-textual-response>"

                checks_ok, check_details, first_error = evaluate_checks(resp, elapsed_ms, step.checks)
                step_success = checks_ok
                if not step_success:
                    success = False
                    if not error_summary:
                        error_summary = f"Step '{step.name}' failed: {first_error}"

                step_results.append({
                    "name": step.name,
                    "method": method,
                    "url": step.url,
                    "status_code": resp.status_code,
                    "response_ms": round(elapsed_ms, 2),
                    "success": step_success,
                    "checks": check_details,
                    "response_excerpt": body_excerpt,
                })

                if not step_success:
                    # stop on first failed step
                    break

            except requests.RequestException as e:
                elapsed_ms = (time.time() - step_start) * 1000.0
                success = False
                error_summary = f"Step '{step.name}' error: {str(e)}"
                step_results.append({
                    "name": step.name,
                    "method": step.method.upper(),
                    "url": step.url,
                    "status_code": None,
                    "response_ms": round(elapsed_ms, 2),
                    "success": False,
                    "checks": [],
                    "response_excerpt": None,
                    "error": str(e),
                })
                break

        finished_at = time.time()
        duration_ms = (finished_at - started_at) * 1000.0

        run_record = self.storage.create_flow_run(
            flow_id=flow.id,
            flow_name=flow.name,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            success=success,
            error_summary=error_summary,
            details={"steps": step_results},
        )

        # persist step runs
        for sr in step_results:
            self.storage.create_step_run(
                flow_run_id=run_record["id"],
                step_name=sr["name"],
                method=sr["method"],
                url=sr["url"],
                status_code=sr.get("status_code"),
                success=sr["success"],
                response_ms=sr["response_ms"],
                error=sr.get("error"),
                response_excerpt=sr.get("response_excerpt"),
            )

        # alerting transitions
        self.alert_manager.evaluate_and_alert(flow, success, error_summary)

        return {
            "id": run_record["id"],
            "flow_id": flow.id,
            "flow_name": flow.name,
            "started_at": run_record["started_at"],
            "finished_at": run_record["finished_at"],
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error_summary": error_summary,
            "steps": step_results,
        }

