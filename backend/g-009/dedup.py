import time
import uuid
import threading


class LocalInFlight:
    def __init__(self):
        self._events = {}
        self._lock = threading.RLock()

    def begin(self, key):
        with self._lock:
            evt = self._events.get(key)
            if evt is None:
                evt = threading.Event()
                self._events[key] = evt
                return True, evt
            else:
                return False, evt

    def done(self, key):
        with self._lock:
            evt = self._events.get(key)
            if evt is not None:
                evt.set()
                self._events.pop(key, None)


class DedupHandle:
    def __init__(self, is_leader):
        self.is_leader = is_leader

    def wait_for_result(self, cache_key, timeout, poll_interval):  # pragma: no cover
        raise NotImplementedError

    def done(self):  # pragma: no cover
        raise NotImplementedError


class RedisDedupHandle(DedupHandle):
    def __init__(self, cache, inflight_key, is_leader):
        super().__init__(is_leader)
        self.cache = cache
        self.inflight_key = inflight_key

    def wait_for_result(self, cache_key, timeout, poll_interval):
        # Poll cache for the result until timeout
        end = time.time() + float(timeout)
        while time.time() < end:
            data = self.cache.get_json(cache_key)
            if data is not None:
                return data
            time.sleep(poll_interval)
        return None

    def done(self):
        # Remove inflight lock
        try:
            self.cache.delete(self.inflight_key)
        except Exception:
            pass


class LocalDedupHandle(DedupHandle):
    def __init__(self, local_inflight, key, is_leader, event):
        super().__init__(is_leader)
        self.local = local_inflight
        self.key = key
        self.event = event

    def wait_for_result(self, cache_key, timeout, poll_interval):
        finished = self.event.wait(timeout)
        if not finished:
            return None
        return self.local_cache_get(cache_key)

    def local_cache_get(self, cache_key):
        # This method is intended to be monkey patched by Deduper to access cache
        raise RuntimeError("Local cache getter not attached")

    def done(self):
        self.local.done(self.key)


class Deduper:
    def __init__(self, cache, config):
        self.cache = cache
        self.config = config
        self.local = LocalInFlight()

    def begin(self, key):
        inflight_key = f"inflight:{key}"
        ttl = self.config.INFLIGHT_TTL_SECONDS

        if self.cache.is_redis:
            rid = str(uuid.uuid4())
            ok = self.cache.setnx(inflight_key, rid, ttl=ttl)
            if ok:
                return RedisDedupHandle(self.cache, inflight_key, True)
            else:
                return RedisDedupHandle(self.cache, inflight_key, False)
        else:
            is_leader, event = self.local.begin(key)
            handle = LocalDedupHandle(self.local, key, is_leader, event)
            # Attach cache getter
            def _get(c_key):
                return self.cache.get_json(c_key)
            handle.local_cache_get = _get
            return handle

