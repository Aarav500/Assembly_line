import json
import logging
import queue
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from urllib import request as urllib_request


class HTTPLogHandler(logging.Handler):
    def __init__(
        self,
        endpoint: str,
        service: Optional[str] = None,
        environment: Optional[str] = None,
        host: Optional[str] = None,
        app_version: Optional[str] = None,
        batch_size: int = 50,
        flush_interval: float = 2.0,
        max_queue: int = 10000,
        timeout: float = 5.0,
    ):
        super().__init__()
        self.endpoint = endpoint.rstrip('/') + '/api/logs'
        self.service = service
        self.environment = environment
        self.host = host or socket.gethostname()
        self.app_version = app_version
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.timeout = timeout
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='HTTPLogSender', daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = self._format_record(record)
            try:
                self._queue.put_nowait(payload)
            except queue.Full:
                # Drop oldest
                try:
                    _ = self._queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._queue.put_nowait(payload)
                except queue.Full:
                    pass
        except Exception:
            # Swallow errors
            pass

    def close(self) -> None:
        try:
            self._stop.set()
            self._thread.join(timeout=2.0)
        except Exception:
            pass
        super().close()

    def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace('+00:00', 'Z')
        msg = record.getMessage()
        base: Dict[str, Any] = {
            'timestamp': ts,
            'level': record.levelname,
            'message': msg,
            'logger': record.name,
            'thread': record.threadName,
            'service': self.service,
            'environment': self.environment,
            'host': self.host,
            'app_version': self.app_version,
        }
        # Extract extra/context
        # Everything not in LogRecord standard attributes is in record.__dict__ as extras
        std = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)).keys())
        extras = {k: v for k, v in record.__dict__.items() if k not in std and k not in base}
        ctx = {}
        # Common convention: request_id, user_id in extras
        if 'request_id' in extras:
            base['request_id'] = extras.get('request_id')
            extras.pop('request_id', None)
        if 'user_id' in extras:
            base['user_id'] = extras.get('user_id')
            extras.pop('user_id', None)
        # Put remaining into context/extra buckets
        base['context'] = ctx
        base['extra'] = extras
        # Exception info
        if record.exc_info:
            import traceback
            tb = ''.join(traceback.format_exception(*record.exc_info))
            base['context']['exception'] = tb
        return base

    def _run(self):
        batch: List[Dict[str, Any]] = []
        last_flush = time.time()
        backoff = 1.0
        while not self._stop.is_set():
            try:
                try:
                    item = self._queue.get(timeout=self.flush_interval)
                    batch.append(item)
                except queue.Empty:
                    pass
                now = time.time()
                if len(batch) >= self.batch_size or (batch and (now - last_flush) >= self.flush_interval):
                    ok = self._flush(batch)
                    if ok:
                        batch.clear()
                        last_flush = now
                        backoff = 1.0
                    else:
                        # Backoff and retry later
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 30.0)
            except Exception:
                time.sleep(1.0)
        # Flush remaining
        if batch:
            self._flush(batch)

    def _flush(self, batch: List[Dict[str, Any]]) -> bool:
        if not batch:
            return True
        data = json.dumps({'entries': batch}).encode('utf-8')
        req = urllib_request.Request(self.endpoint, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False


if __name__ == '__main__':
    # Example usage
    import sys

    endpoint = 'http://localhost:5000'
    handler = HTTPLogHandler(endpoint=endpoint, service='example-app', environment='dev', app_version='1.0.0')

    logger = logging.getLogger('example')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    logger.info('Application started', extra={'request_id': 'req-123', 'user_id': 'u-42'})
    try:
        1/0
    except ZeroDivisionError:
        logger.exception('An error occurred', extra={'request_id': 'req-123'})

    logger.debug('Debug detail', extra={'feature': 'test', 'step': 2})

    print('Sent a few logs to the server at', endpoint)
    time.sleep(3)

