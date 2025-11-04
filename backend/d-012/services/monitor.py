from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import random


class Monitor:
    def __init__(self):
        # failure_injections[(service, version)] = {reason: str, error_code: str?, flaky: bool?}
        self.failure_injections: Dict[tuple, Dict[str, Any]] = {}

    def inject_failure(self, service: str, version: str, metadata: Dict[str, Any]):
        self.failure_injections[(service, version)] = metadata or {'reason': 'unknown'}

    def clear_failure(self, service: str, version: str):
        self.failure_injections.pop((service, version), None)

    def health_check(self, service: str, version: str) -> Tuple[bool, Dict[str, Any]]:
        key = (service, version)
        injected = self.failure_injections.get(key)
        # Simulated metrics
        metrics = {
            'cpu_percent': round(random.uniform(3, 95), 1),
            'memory_mb': round(random.uniform(100, 1024), 1),
            'latency_ms_p50': round(random.uniform(5, 800), 1),
            'latency_ms_p99': round(random.uniform(30, 2000), 1),
            'error_rate_perc': round(random.uniform(0, 30), 2),
        }
        timestamp = datetime.utcnow().isoformat() + 'Z'
        if injected:
            details = {
                'ok': False,
                'ts': timestamp,
                'reason': injected.get('reason', 'injected_failure'),
                'error_code': injected.get('error_code'),
                'metrics': metrics,
                'checks': [
                    {'name': 'health_endpoint', 'status': 'fail'},
                    {'name': 'db_connectivity', 'status': 'unknown'},
                ]
            }
            return False, details
        # basic threshold-based failure simulation
        if metrics['error_rate_perc'] > 10 or metrics['latency_ms_p99'] > 1500:
            details = {
                'ok': False,
                'ts': timestamp,
                'reason': 'automated_threshold_breach',
                'metrics': metrics,
                'checks': [
                    {'name': 'health_endpoint', 'status': 'degraded'},
                    {'name': 'db_connectivity', 'status': 'pass'},
                ]
            }
            return False, details
        return True, {
            'ok': True,
            'ts': timestamp,
            'metrics': metrics,
            'checks': [
                {'name': 'health_endpoint', 'status': 'pass'},
                {'name': 'db_connectivity', 'status': 'pass'},
            ]
        }

