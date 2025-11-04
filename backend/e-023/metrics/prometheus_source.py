import requests
from .base import MetricsSource


class PrometheusMetrics(MetricsSource):
    def __init__(self, base_url: str, query: str = None, timeout_seconds: int = 5):
        if not base_url:
            raise ValueError('Prometheus base_url required')
        self.base_url = base_url.rstrip('/')
        self.query_tpl = query  # optional template; if None, metric_id is the query
        self.timeout = timeout_seconds

    def get_queue_depth(self, metric_id: str) -> int:
        query = self.query_tpl or metric_id
        url = f"{self.base_url}/api/v1/query"
        resp = requests.get(url, params={'query': query}, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != 'success':
            raise RuntimeError(f"Prometheus query failed: {data}")
        results = data.get('data', {}).get('result', [])
        if not results:
            return 0
        # Sum all series values if multiple
        total = 0
        for r in results:
            v = r.get('value') or r.get('values')
            if isinstance(v, list):
                # instant vector has [timestamp, value]
                if len(v) >= 2 and isinstance(v[1], str):
                    total += float(v[1])
                else:
                    # range vector last sample
                    last = v[-1]
                    total += float(last[1])
        return int(total)

