import os
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _getenv_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except Exception:
        return default


def _getenv_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: List[str] = field(default_factory=list)


@dataclass
class AlertsConfig:
    slack_webhook_url: str = ""
    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass
class PrometheusConfig:
    url: str = "http://prometheus:9090"
    verify_tls: bool = True
    timeout_seconds: int = 15
    step: str = "5m"


@dataclass
class BudgetConfig:
    monthly_amount: float = 1000.0
    warn_threshold: float = 0.8
    crit_threshold: float = 0.95


@dataclass
class RatesConfig:
    cpu_core_hour: float = 0.031
    memory_gb_hour: float = 0.004
    network_gb: float = 0.09
    storage_gb_hour: float = 0.0001389


@dataclass
class QueriesConfig:
    cpu_increase_expr: str = (
        "sum by (namespace) (increase(container_cpu_usage_seconds_total{image!=''}[{window}]))"
    )
    cpu_usage_series_expr: str = (
        "sum by (namespace,pod,container) (rate(container_cpu_usage_seconds_total{image!=''}[5m]))"
    )
    memory_avg_expr: str = (
        "sum by (namespace) (avg_over_time(container_memory_working_set_bytes{image!=''}[{window}]))"
    )
    memory_usage_series_expr: str = (
        "sum by (namespace,pod,container) (container_memory_working_set_bytes{image!=''})"
    )
    network_egress_increase_expr: str = (
        "sum by (namespace) (increase(container_network_transmit_bytes_total{image!=''}[{window}]))"
    )
    storage_avg_expr: str = (
        "sum by (namespace) (avg_over_time(kubelet_volume_stats_used_bytes[{window}]))"
    )
    cpu_requests_exprs: List[str] = field(
        default_factory=lambda: [
            "sum by (namespace,pod,container) (kube_pod_container_resource_requests_cpu_cores)",
            "sum by (namespace,pod,container) (rate(container_spec_cpu_quota[5m]) / rate(container_spec_cpu_period[5m]))",
        ]
    )
    memory_requests_exprs: List[str] = field(
        default_factory=lambda: [
            "sum by (namespace,pod,container) (kube_pod_container_resource_requests_memory_bytes)",
        ]
    )


@dataclass
class Config:
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)
    currency: str = "USD"
    rates: RatesConfig = field(default_factory=RatesConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    labels: Dict[str, str] = field(default_factory=lambda: {"namespace": "namespace"})
    namespace_breakdown: bool = True
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    queries: QueriesConfig = field(default_factory=QueriesConfig)


def load_config(path: str = "config.yaml") -> Config:
    cfg = Config()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Merge dict recursively
    def deep_update(d: Any, u: Any) -> Any:
        if isinstance(d, dict) and isinstance(u, dict):
            for k, v in u.items():
                d[k] = deep_update(d.get(k), v)
            return d
        else:
            return u if u is not None else d

    base = {
        "prometheus": cfg.prometheus.__dict__,
        "currency": cfg.currency,
        "rates": cfg.rates.__dict__,
        "budget": cfg.budget.__dict__,
        "labels": cfg.labels,
        "namespace_breakdown": cfg.namespace_breakdown,
        "alerts": {
            "slack_webhook_url": cfg.alerts.slack_webhook_url,
            "email": cfg.alerts.email.__dict__,
        },
        "queries": {
            "cpu_increase_expr": cfg.queries.cpu_increase_expr,
            "cpu_usage_series_expr": cfg.queries.cpu_usage_series_expr,
            "memory_avg_expr": cfg.queries.memory_avg_expr,
            "memory_usage_series_expr": cfg.queries.memory_usage_series_expr,
            "network_egress_increase_expr": cfg.queries.network_egress_increase_expr,
            "storage_avg_expr": cfg.queries.storage_avg_expr,
            "cpu_requests_exprs": cfg.queries.cpu_requests_exprs,
            "memory_requests_exprs": cfg.queries.memory_requests_exprs,
        },
    }

    merged = deep_update(base, data)

    # Environment overrides
    merged["prometheus"]["url"] = os.getenv("PROMETHEUS_URL", merged["prometheus"]["url"]) 
    merged["currency"] = os.getenv("CURRENCY", merged["currency"]) 
    merged["rates"]["cpu_core_hour"] = _getenv_float("RATE_CPU_CORE_HOUR", merged["rates"]["cpu_core_hour"]) 
    merged["rates"]["memory_gb_hour"] = _getenv_float("RATE_MEMORY_GB_HOUR", merged["rates"]["memory_gb_hour"]) 
    merged["rates"]["network_gb"] = _getenv_float("RATE_NETWORK_GB", merged["rates"]["network_gb"]) 
    merged["rates"]["storage_gb_hour"] = _getenv_float("RATE_STORAGE_GB_HOUR", merged["rates"]["storage_gb_hour"]) 
    merged["budget"]["monthly_amount"] = _getenv_float("BUDGET_MONTHLY_AMOUNT", merged["budget"]["monthly_amount"]) 
    merged["namespace_breakdown"] = _getenv_bool("NAMESPACE_BREAKDOWN", merged["namespace_breakdown"]) 

    # Build dataclasses
    cfg.prometheus = PrometheusConfig(**merged["prometheus"]) 
    cfg.currency = merged["currency"]
    cfg.rates = RatesConfig(**merged["rates"]) 
    cfg.budget = BudgetConfig(**merged["budget"]) 
    cfg.labels = merged.get("labels", {"namespace": "namespace"})
    cfg.namespace_breakdown = merged.get("namespace_breakdown", True)

    email_cfg = EmailConfig(**merged["alerts"].get("email", {}))
    cfg.alerts = AlertsConfig(
        slack_webhook_url=merged["alerts"].get("slack_webhook_url", ""),
        email=email_cfg,
    )

    q = merged.get("queries", {})
    cfg.queries = QueriesConfig(
        cpu_increase_expr=q.get("cpu_increase_expr", cfg.queries.cpu_increase_expr),
        cpu_usage_series_expr=q.get("cpu_usage_series_expr", cfg.queries.cpu_usage_series_expr),
        memory_avg_expr=q.get("memory_avg_expr", cfg.queries.memory_avg_expr),
        memory_usage_series_expr=q.get("memory_usage_series_expr", cfg.queries.memory_usage_series_expr),
        network_egress_increase_expr=q.get("network_egress_increase_expr", cfg.queries.network_egress_increase_expr),
        storage_avg_expr=q.get("storage_avg_expr", cfg.queries.storage_avg_expr),
        cpu_requests_exprs=q.get("cpu_requests_exprs", cfg.queries.cpu_requests_exprs),
        memory_requests_exprs=q.get("memory_requests_exprs", cfg.queries.memory_requests_exprs),
    )

    return cfg

