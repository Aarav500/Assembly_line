from __future__ import annotations
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .config import Config
from .prom_client import PrometheusClient


@dataclass
class CostBreakdown:
    total: float
    cpu: float
    memory: float
    network: float
    storage: float
    per_namespace: Dict[str, Dict[str, float]]  # {ns: {resource: cost}}


def seconds_to_prom_duration(seconds: int) -> str:
    # Use seconds with 's' suffix to keep generic
    return f"{int(max(seconds, 1))}s"


def safe_float(v: str) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


class CostModel:
    def __init__(self, cfg: Config, prom: PrometheusClient):
        self.cfg = cfg
        self.prom = prom

    async def compute_costs(self, window_seconds: int, end_ts: float | None = None) -> CostBreakdown:
        if end_ts is None:
            end_ts = time.time()
        currency = self.cfg.currency
        labels_ns = self.cfg.labels.get("namespace", "namespace")
        window = seconds_to_prom_duration(window_seconds)

        # CPU core-hours using increase over full window
        cpu_expr = self.cfg.queries.cpu_increase_expr.format(window=window)
        cpu_res = await self.prom.query(cpu_expr)
        cpu_vec = self.prom.extract_vector(cpu_res)
        per_ns_cpu_core_seconds: Dict[str, float] = {}
        for series in cpu_vec:
            ns = series.get("metric", {}).get(labels_ns, "unknown")
            val = safe_float(series.get("value", [None, "0"]) [1])
            per_ns_cpu_core_seconds[ns] = per_ns_cpu_core_seconds.get(ns, 0.0) + val
        per_ns_cpu_core_hours = {ns: v / 3600.0 for ns, v in per_ns_cpu_core_seconds.items()}
        cpu_cost_per_ns = {ns: v * self.cfg.rates.cpu_core_hour for ns, v in per_ns_cpu_core_hours.items()}
        cpu_total_cost = sum(cpu_cost_per_ns.values())

        # Memory GB-hours using avg_over_time * window
        mem_expr = self.cfg.queries.memory_avg_expr.format(window=window)
        mem_res = await self.prom.query(mem_expr)
        mem_vec = self.prom.extract_vector(mem_res)
        per_ns_mem_avg_bytes: Dict[str, float] = {}
        for series in mem_vec:
            ns = series.get("metric", {}).get(labels_ns, "unknown")
            val = safe_float(series.get("value", [None, "0"]) [1])
            per_ns_mem_avg_bytes[ns] = per_ns_mem_avg_bytes.get(ns, 0.0) + val
        per_ns_mem_byte_hours = {ns: v * (window_seconds / 3600.0) for ns, v in per_ns_mem_avg_bytes.items()}
        gb = 1024.0 ** 3
        per_ns_mem_gb_hours = {ns: v / gb for ns, v in per_ns_mem_byte_hours.items()}
        mem_cost_per_ns = {ns: v * self.cfg.rates.memory_gb_hour for ns, v in per_ns_mem_gb_hours.items()}
        mem_total_cost = sum(mem_cost_per_ns.values())

        # Network GB using increase over full window
        net_expr = self.cfg.queries.network_egress_increase_expr.format(window=window)
        net_res = await self.prom.query(net_expr)
        net_vec = self.prom.extract_vector(net_res)
        per_ns_net_bytes: Dict[str, float] = {}
        for series in net_vec:
            ns = series.get("metric", {}).get(labels_ns, "unknown")
            val = safe_float(series.get("value", [None, "0"]) [1])
            per_ns_net_bytes[ns] = per_ns_net_bytes.get(ns, 0.0) + val
        per_ns_net_gb = {ns: v / gb for ns, v in per_ns_net_bytes.items()}
        net_cost_per_ns = {ns: v * self.cfg.rates.network_gb for ns, v in per_ns_net_gb.items()}
        net_total_cost = sum(net_cost_per_ns.values())

        # Storage GB-hours using avg_over_time * window (optional)
        stor_expr = self.cfg.queries.storage_avg_expr.format(window=window)
        stor_res = await self.prom.query(stor_expr)
        stor_vec = self.prom.extract_vector(stor_res)
        per_ns_storage_avg_bytes: Dict[str, float] = {}
        for series in stor_vec:
            ns = series.get("metric", {}).get(labels_ns, "unknown")
            val = safe_float(series.get("value", [None, "0"]) [1])
            per_ns_storage_avg_bytes[ns] = per_ns_storage_avg_bytes.get(ns, 0.0) + val
        per_ns_storage_byte_hours = {ns: v * (window_seconds / 3600.0) for ns, v in per_ns_storage_avg_bytes.items()}
        per_ns_storage_gb_hours = {ns: v / gb for ns, v in per_ns_storage_byte_hours.items()}
        stor_cost_per_ns = {ns: v * self.cfg.rates.storage_gb_hour for ns, v in per_ns_storage_gb_hours.items()}
        stor_total_cost = sum(stor_cost_per_ns.values())

        per_ns_costs: Dict[str, Dict[str, float]] = {}
        all_ns = set(cpu_cost_per_ns.keys()) | set(mem_cost_per_ns.keys()) | set(net_cost_per_ns.keys()) | set(stor_cost_per_ns.keys())
        for ns in all_ns:
            per_ns_costs[ns] = {
                "cpu": cpu_cost_per_ns.get(ns, 0.0),
                "memory": mem_cost_per_ns.get(ns, 0.0),
                "network": net_cost_per_ns.get(ns, 0.0),
                "storage": stor_cost_per_ns.get(ns, 0.0),
            }

        total_cost = cpu_total_cost + mem_total_cost + net_total_cost + stor_total_cost
        return CostBreakdown(
            total=total_cost,
            cpu=cpu_total_cost,
            memory=mem_total_cost,
            network=net_total_cost,
            storage=stor_total_cost,
            per_namespace=per_ns_costs,
        )

