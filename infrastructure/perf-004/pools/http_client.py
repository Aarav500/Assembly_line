import threading
import time
from urllib.parse import urlparse

import requests
from flask import current_app
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from monitoring.metrics import (
    http_client_in_flight_gauge,
    http_client_request_duration_seconds,
    http_client_requests_total,
    http_client_errors_total,
)
from utils.rate_limiter import TokenBucket


class HttpClient:
    def __init__(self, *, pool_connections: int, pool_maxsize: int, max_retries: int,
                 concurrency_limit: int, rate_limit_per_sec: float, rate_limit_burst: float,
                 default_timeout: float = 10.0):
        self.session: Session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=0.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(pool_connections=pool_connections, pool_maxsize=pool_maxsize, max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self._sema = threading.BoundedSemaphore(concurrency_limit)
        self._rate = TokenBucket(rate=rate_limit_per_sec, capacity=rate_limit_burst)
        self._default_timeout = default_timeout

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def request(self, method: str, url: str, timeout: float = None, **kwargs) -> requests.Response:
        timeout = timeout or self._default_timeout
        acquired = self._sema.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError("HTTP client concurrency limit exceeded")
        token_ok = self._rate.acquire(timeout=timeout)
        if not token_ok:
            self._sema.release()
            raise TimeoutError("HTTP client rate limit wait timeout")
        http_client_in_flight_gauge.inc()
        start = time.perf_counter()
        host_label = urlparse(url).hostname or "unknown"
        try:
            resp = self.session.request(method=method, url=url, timeout=timeout, **kwargs)
            elapsed = time.perf_counter() - start
            status_label = str(resp.status_code)
            http_client_request_duration_seconds.labels(method=method.upper(), host=host_label, status=status_label).observe(elapsed)
            http_client_requests_total.labels(method=method.upper(), host=host_label, status=status_label).inc()
            return resp
        except requests.RequestException as e:
            elapsed = time.perf_counter() - start
            http_client_errors_total.labels(method=method.upper(), host=host_label, error=e.__class__.__name__).inc()
            http_client_request_duration_seconds.labels(method=method.upper(), host=host_label, status="error").observe(elapsed)
            raise
        finally:
            http_client_in_flight_gauge.dec()
            self._sema.release()

    # Convenience methods
    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)


def init_http_client(app):
    client = HttpClient(
        pool_connections=app.config.get("HTTP_POOL_CONNECTIONS", 10),
        pool_maxsize=app.config.get("HTTP_POOL_MAXSIZE", 50),
        max_retries=app.config.get("HTTP_MAX_RETRIES", 2),
        concurrency_limit=app.config.get("HTTP_CONCURRENCY_LIMIT", 20),
        rate_limit_per_sec=app.config.get("HTTP_RATE_LIMIT_PER_SEC", 20.0),
        rate_limit_burst=app.config.get("HTTP_RATE_LIMIT_BURST", 40.0),
        default_timeout=app.config.get("HTTP_DEFAULT_TIMEOUT", 10.0),
    )
    app.extensions["http_client"] = client


def shutdown_http_client(app):
    client: HttpClient = app.extensions.get("http_client")
    if client:
        client.close()


def get_http_client() -> HttpClient:
    client: HttpClient = current_app.extensions.get("http_client")
    if client is None:
        raise RuntimeError("HTTP client not initialized")
    return client

