from __future__ import annotations
import math
import numpy as np
import time
from typing import Dict, List, Tuple

from .config import Config
from .prom_client import PrometheusClient


def _safe_float(s: str) -> float:
    try:
        return float(s)
    except Exception:
        return 0.0


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(np.percentile(values, 95))


class Optimizer:
    def __init__(self, cfg: Config, prom: PrometheusClient):
        self.cfg = cfg
        self.prom = prom

    async def fetch_usage_series(self, start_ts: float, end_ts: float, step: str) -> Tuple[Dict[Tuple[str, str, str], List[Tuple[float, float]]], Dict[Tuple[str, str, str], List[Tuple[float, float]]]]:
        # CPU cores usage rate series per container
        cpu_expr = self.cfg.queries.cpu_usage_series_expr
        mem_expr = self.cfg.queries.memory_usage_series_expr
        cpu_res = await self.prom.query_range(cpu_expr, start_ts, end_ts, step)
        mem_res = await self.prom.query_range(mem_expr, start_ts, end_ts, step)

        cpu_series: Dict[Tuple[str, str, str], List[Tuple[float, float]]] = {}
        mem_series: Dict[Tuple[str, str, str], List[Tuple[float, float]]] = {}

        for s in self.prom.extract_matrix(cpu_res):
            m = s.get("metric", {})
            ns = m.get(self.cfg.labels.get("namespace", "namespace"), "unknown")
            pod = m.get("pod", m.get("pod_name", "unknown"))
            ctr = m.get("container", m.get("container_name", "unknown"))
            key = (ns, pod, ctr)
            cpu_series[key] = [(float(t), _safe_float(v)) for t, v in s.get("values", [])]

        for s in self.prom.extract_matrix(mem_res):
            m = s.get("metric", {})
            ns = m.get(self.cfg.labels.get("namespace", "namespace"), "unknown")
            pod = m.get("pod", m.get("pod_name", "unknown"))
            ctr = m.get("container", m.get("container_name", "unknown"))
            key = (ns, pod, ctr)
            mem_series[key] = [(float(t), _safe_float(v)) for t, v in s.get("values", [])]

        return cpu_series, mem_series

    async def fetch_requests(self) -> Tuple[Dict[Tuple[str, str, str], float], Dict[Tuple[str, str, str], float]]:
        cpu_requests: Dict[Tuple[str, str, str], float] = {}
        mem_requests: Dict[Tuple[str, str, str], float] = {}

        # Try expressions in order until we get any
        for expr in self.cfg.queries.cpu_requests_exprs:
            res = await self.prom.query(expr)
            vec = self.prom.extract_vector(res)
            if vec:
                for s in vec:
                    m = s.get("metric", {})
                    ns = m.get(self.cfg.labels.get("namespace", "namespace"), "unknown")
                    pod = m.get("pod", m.get("pod_name", "unknown"))
                    ctr = m.get("container", m.get("container_name", "unknown"))
                    key = (ns, pod, ctr)
                    cpu_requests[key] = _safe_float(s.get("value", [None, "0"]) [1])
                break
        for expr in self.cfg.queries.memory_requests_exprs:
            res = await self.prom.query(expr)
            vec = self.prom.extract_vector(res)
            if vec:
                for s in vec:
                    m = s.get("metric", {})
                    ns = m.get(self.cfg.labels.get("namespace", "namespace"), "unknown")
                    pod = m.get("pod", m.get("pod_name", "unknown"))
                    ctr = m.get("container", m.get("container_name", "unknown"))
                    key = (ns, pod, ctr)
                    mem_requests[key] = _safe_float(s.get("value", [None, "0"]) [1])
                break
        return cpu_requests, mem_requests

    async def compute_recommendations(self, start_ts: float, end_ts: float, step: str) -> Dict[str, any]:
        cpu_series, mem_series = await self.fetch_usage_series(start_ts, end_ts, step)
        cpu_requests, mem_requests = await self.fetch_requests()

        recommendations: List[Dict[str, any]] = []
        underutilized = 0
        overutilized = 0
        potential_savings_cpu = 0.0
        potential_savings_mem = 0.0

        hours = max(1.0, (end_ts - start_ts) / 3600.0)
        gb = 1024.0 ** 3

        # Analyze per container
        keys = set(cpu_series.keys()) | set(mem_series.keys()) | set(cpu_requests.keys()) | set(mem_requests.keys())
        for key in keys:
            ns, pod, ctr = key
            cpu_vals = [v for _, v in cpu_series.get(key, []) if v >= 0]
            mem_vals = [v for _, v in mem_series.get(key, []) if v >= 0]

            cpu_p95 = _p95(cpu_vals) if cpu_vals else 0.0  # cores
            mem_p95_bytes = _p95(mem_vals) if mem_vals else 0.0
            mem_p95_gb = mem_p95_bytes / gb

            req_cpu = cpu_requests.get(key, 0.0)
            req_mem_bytes = mem_requests.get(key, 0.0)
            req_mem_gb = req_mem_bytes / gb

            rec: Dict[str, any] = {
                "namespace": ns,
                "pod": pod,
                "container": ctr,
                "cpu_p95_cores": cpu_p95,
                "mem_p95_gb": mem_p95_gb,
                "req_cpu_cores": req_cpu,
                "req_mem_gb": req_mem_gb,
                "actions": [],
            }

            # Rightsizing down recommendation if request is significantly higher than p95
            if req_cpu > 0 and cpu_p95 < 0.5 * req_cpu:
                target = max(cpu_p95 * 1.2, 0.05)  # leave headroom
                savings_core_hours = max(req_cpu - target, 0.0) * hours
                potential_savings_cpu += savings_core_hours * self.cfg.rates.cpu_core_hour
                rec["actions"].append({
                    "type": "rightsizing",
                    "resource": "cpu",
                    "current_request_cores": req_cpu,
                    "suggested_request_cores": round(target, 3),
                    "est_monthly_savings": round(savings_core_hours * self.cfg.rates.cpu_core_hour, 4),
                })
                underutilized += 1

            if req_mem_gb > 0 and mem_p95_gb < 0.5 * req_mem_gb:
                target_gb = max(mem_p95_gb * 1.2, 0.05)
                savings_gb_hours = max(req_mem_gb - target_gb, 0.0) * hours
                potential_savings_mem += savings_gb_hours * self.cfg.rates.memory_gb_hour
                rec["actions"].append({
                    "type": "rightsizing",
                    "resource": "memory",
                    "current_request_gb": req_mem_gb,
                    "suggested_request_gb": round(target_gb, 3),
                    "est_monthly_savings": round(savings_gb_hours * self.cfg.rates.memory_gb_hour, 4),
                })
                underutilized += 1

            # Overutilization if p95 exceeds request notably
            if req_cpu > 0 and cpu_p95 > 0.9 * req_cpu:
                rec["actions"].append({
                    "type": "overutilized",
                    "resource": "cpu",
                    "message": "CPU p95 near or above request; consider increasing requests/limits",
                })
                overutilized += 1

            if req_mem_gb > 0 and mem_p95_gb > 0.9 * req_mem_gb:
                rec["actions"].append({
                    "type": "overutilized",
                    "resource": "memory",
                    "message": "Memory p95 near or above request; consider increasing requests/limits",
                })
                overutilized += 1

            if rec["actions"]:
                recommendations.append(rec)

        return {
            "generated_at": int(time.time()),
            "summary": {
                "underutilized_count": underutilized,
                "overutilized_count": overutilized,
                "potential_savings_cpu": potential_savings_cpu,
                "potential_savings_memory": potential_savings_mem,
                "potential_savings_total": potential_savings_cpu + potential_savings_mem,
                "currency": self.cfg.currency,
            },
            "recommendations": recommendations,
        }

