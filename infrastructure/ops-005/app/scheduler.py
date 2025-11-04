from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import Config
from .prom_client import PrometheusClient
from .cost_model import CostModel
from .optimizer import Optimizer
from .metrics import (
    cost_total_gauge,
    cost_breakdown_gauge,
    cost_namespace_gauge,
    budget_amount_gauge,
    budget_spent_gauge,
    budget_remaining_gauge,
    budget_alert_gauge,
    budget_forecast_gauge,
    recommended_savings_gauge,
    recommended_savings_breakdown_gauge,
    underutilized_count_gauge,
    overutilized_count_gauge,
)
from .alerter import Alerter


def month_start_end(now: Optional[datetime] = None):
    if now is None:
        now = datetime.now(timezone.utc)
    start = datetime(year=now.year, month=now.month, day=1, tzinfo=timezone.utc)
    if now.month == 12:
        next_month = datetime(year=now.year + 1, month=1, day=1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year=now.year, month=now.month + 1, day=1, tzinfo=timezone.utc)
    return start, next_month


@dataclass
class AppState:
    last_recommendations: Dict[str, Any] = field(default_factory=dict)
    last_budget_alert_level: Optional[str] = None


class Scheduler:
    def __init__(self, cfg: Config, prom: PrometheusClient, state: AppState):
        self.cfg = cfg
        self.prom = prom
        self.state = state
        self.cost_model = CostModel(cfg, prom)
        self.optimizer = Optimizer(cfg, prom)
        self.alerter = Alerter(cfg.alerts)
        self.interval_seconds = 300  # 5 minutes

    async def tick(self):
        now_dt = datetime.now(timezone.utc)
        start_month, next_month = month_start_end(now_dt)
        start_ts = start_month.timestamp()
        end_ts = now_dt.timestamp()
        window_seconds = int(end_ts - start_ts)
        step = self.cfg.prometheus.step

        # Compute costs for MTD window
        breakdown = await self.cost_model.compute_costs(window_seconds, end_ts=end_ts)
        currency = self.cfg.currency

        # Update metrics for costs
        cost_total_gauge.labels(currency=currency).set(breakdown.total)
        cost_breakdown_gauge.labels(resource="cpu", currency=currency).set(breakdown.cpu)
        cost_breakdown_gauge.labels(resource="memory", currency=currency).set(breakdown.memory)
        cost_breakdown_gauge.labels(resource="network", currency=currency).set(breakdown.network)
        cost_breakdown_gauge.labels(resource="storage", currency=currency).set(breakdown.storage)

        if self.cfg.namespace_breakdown:
            for ns, parts in breakdown.per_namespace.items():
                for rsrc, val in parts.items():
                    cost_namespace_gauge.labels(namespace=ns, resource=rsrc, currency=currency).set(val)

        # Budget metrics and alerts
        monthly_budget = self.cfg.budget.monthly_amount
        elapsed_ratio = max(1e-6, (end_ts - start_ts) / (next_month.timestamp() - start_ts))
        forecast_eom = breakdown.total / elapsed_ratio

        budget_amount_gauge.labels(currency=currency).set(monthly_budget)
        budget_spent_gauge.labels(currency=currency).set(breakdown.total)
        budget_remaining_gauge.labels(currency=currency).set(monthly_budget - breakdown.total)
        budget_forecast_gauge.labels(currency=currency).set(forecast_eom)

        warn_level = None
        if monthly_budget > 0:
            pct = breakdown.total / monthly_budget
            if pct >= self.cfg.budget.crit_threshold:
                warn_level = "crit"
            elif pct >= self.cfg.budget.warn_threshold:
                warn_level = "warn"
        # Reset gauges
        budget_alert_gauge.labels(level="warn").set(1.0 if warn_level == "warn" else 0.0)
        budget_alert_gauge.labels(level="crit").set(1.0 if warn_level == "crit" else 0.0)

        if warn_level and warn_level != self.state.last_budget_alert_level:
            msg = (
                f"MTD spend {breakdown.total:.2f} {currency} reached {warn_level.upper()} threshold of budget {monthly_budget:.2f} {currency}. "
                f"Forecast EOM: {forecast_eom:.2f} {currency}."
            )
            await self.alerter.alert_budget(warn_level, msg)
            self.state.last_budget_alert_level = warn_level
        elif not warn_level:
            self.state.last_budget_alert_level = None

        # Recommendations
        rec = await self.optimizer.compute_recommendations(start_ts, end_ts, step)
        self.state.last_recommendations = rec

        # Update rec metrics
        savings_total = rec["summary"]["potential_savings_total"]
        savings_cpu = rec["summary"]["potential_savings_cpu"]
        savings_mem = rec["summary"]["potential_savings_memory"]
        recommended_savings_gauge.labels(currency=currency).set(savings_total)
        recommended_savings_breakdown_gauge.labels(resource="cpu", currency=currency).set(savings_cpu)
        recommended_savings_breakdown_gauge.labels(resource="memory", currency=currency).set(savings_mem)
        underutilized_count_gauge.labels(kind="container").set(rec["summary"]["underutilized_count"])
        overutilized_count_gauge.labels(kind="container").set(rec["summary"]["overutilized_count"])

    async def run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                # swallow exceptions to keep scheduler running
                pass
            await asyncio.sleep(self.interval_seconds)

