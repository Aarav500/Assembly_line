import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Tuple

import redis

from .config import REDIS_URL, CACHE_MONITOR_PORT


def _collect_metrics(r: redis.Redis) -> Dict[str, Dict[str, int]]:
    namespaces: Dict[str, Dict[str, int]] = {}
    cursor = 0
    pattern = "cache:*:metrics"
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pattern, count=200)
        for key in keys:
            ns = _ns_from_metrics_key(key)
            if not ns:
                continue
            m = r.hgetall(key)
            mdict: Dict[str, int] = {}
            for k, v in m.items():
                k2 = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
                try:
                    mdict[k2] = int(v)
                except Exception:
                    mdict[k2] = 0
            hits = mdict.get("hits", 0)
            misses = mdict.get("misses", 0)
            total = hits + misses
            mdict["hit_rate"] = (hits / total) if total > 0 else 0.0
            namespaces[ns] = mdict
        if cursor == 0:
            break
    return namespaces


def _ns_from_metrics_key(key: bytes) -> str:
    # key format: cache:{ns}:metrics
    try:
        k = key.decode("utf-8")
        parts = k.split(":")
        if len(parts) >= 3 and parts[0] == "cache" and parts[-1] == "metrics":
            return parts[1]
    except Exception:
        pass
    return ""


class MetricsHandler(BaseHTTPRequestHandler):
    r: redis.Redis = redis.Redis.from_url(REDIS_URL, decode_responses=False)

    def _send_json(self, status: int, payload: Dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        # silence default logging
        return

    def do_GET(self):
        if self.path.startswith("/metrics"):
            namespaces = _collect_metrics(self.r)
            self._send_json(200, {"timestamp": time.time(), "namespaces": namespaces})
            return
        if self.path.startswith("/health"):
            try:
                self.r.ping()
                self._send_json(200, {"status": "ok"})
            except Exception as e:
                self._send_json(500, {"status": "error", "error": str(e)})
            return
        self._send_json(404, {"error": "not found"})


def start_monitor_server(port: int = CACHE_MONITOR_PORT) -> Tuple[HTTPServer, threading.Thread]:
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t

