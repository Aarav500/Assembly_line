from .base import MetricsSource
from .redis_source import RedisMetrics
from .prometheus_source import PrometheusMetrics
from .mock_source import MockMetrics


def metrics_source_from_config(cfg) -> MetricsSource:
    t = (cfg.type or '').lower()
    if t == 'redis':
        return RedisMetrics(**cfg.params)
    if t == 'prometheus':
        return PrometheusMetrics(**cfg.params)
    if t == 'mock':
        return MockMetrics(**cfg.params)
    raise ValueError(f"Unsupported metrics source: {cfg.type}")

