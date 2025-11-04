import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import threading
from flask import Flask, request, jsonify

from cache_store import InMemoryCache, TTLPolicy, CacheEntry
from embedding_provider import EmbeddingProvider


class EmbeddingCache:
    def __init__(self, provider: EmbeddingProvider, store: InMemoryCache):
        self.provider = provider
        self.store = store
        self.lock = threading.Lock()
        self.refreshing_keys = set()
        self.metrics = {
            "hits": 0,
            "misses": 0,
            "recomputes": 0,
            "stale_served": 0,
            "background_refreshes": 0,
            "forced_refreshes": 0,
        }

    def _now(self):
        return time.time()

    def _start_background_refresh(self, key: str, text: str, model: str, ttl_seconds: int, stale_ttl_seconds: int):
        def _refresh():
            try:
                embedding = self.provider.generate_embedding(text=text, model=model)
                entry = CacheEntry(
                    value=embedding,
                    policy=TTLPolicy.STALE_WHILE_REVALIDATE,
                    created_at=self._now(),
                    last_access=self._now(),
                    expires_at=self._now() + ttl_seconds,
                    ttl_seconds=ttl_seconds,
                    stale_ttl_seconds=stale_ttl_seconds,
                )
                self.store.set_entry(key, entry)
            finally:
                with self.lock:
                    self.refreshing_keys.discard(key)

        with self.lock:
            if key in self.refreshing_keys:
                return
            self.refreshing_keys.add(key)
            self.metrics["background_refreshes"] += 1
        t = threading.Thread(target=_refresh, daemon=True)
        t.start()

    def embed(self, text: str, model: str, policy: str = "fixed", ttl_seconds: int = 86400, stale_ttl_seconds: int = 43200, force_refresh: bool = False):
        policy_enum = TTLPolicy(policy)
        key = self.store.make_key(text=text, model=model)
        now = self._now()

        if force_refresh:
            embedding = self.provider.generate_embedding(text=text, model=model)
            entry = self._build_entry(policy_enum, embedding, ttl_seconds, stale_ttl_seconds)
            self.store.set_entry(key, entry)
            self.metrics["forced_refreshes"] += 1
            self.metrics["recomputes"] += 1
            return self._response(key, embedding, entry, source="computed", hit=False, recomputed=True, stale_served=False)

        entry = self.store.get_entry(key)
        if entry is None:
            # Miss, compute
            embedding = self.provider.generate_embedding(text=text, model=model)
            entry = self._build_entry(policy_enum, embedding, ttl_seconds, stale_ttl_seconds)
            self.store.set_entry(key, entry)
            self.metrics["misses"] += 1
            self.metrics["recomputes"] += 1
            return self._response(key, embedding, entry, source="computed", hit=False, recomputed=True, stale_served=False)

        # Entry exists; apply policy rules
        if entry.policy == TTLPolicy.FOREVER or policy_enum == TTLPolicy.FOREVER:
            # treat as evergreen
            entry.last_access = now
            entry.policy = TTLPolicy.FOREVER
            self.store.set_entry(key, entry)
            self.metrics["hits"] += 1
            return self._response(key, entry.value, entry, source="cache", hit=True, recomputed=False, stale_served=False)

        if policy_enum == TTLPolicy.SLIDING or entry.policy == TTLPolicy.SLIDING:
            # Sliding TTL
            if entry.expires_at is None or now <= entry.expires_at:
                entry.last_access = now
                entry.policy = TTLPolicy.SLIDING
                entry.expires_at = now + ttl_seconds
                entry.ttl_seconds = ttl_seconds
                self.store.set_entry(key, entry)
                self.metrics["hits"] += 1
                return self._response(key, entry.value, entry, source="cache", hit=True, recomputed=False, stale_served=False)
            else:
                # expired -> recompute
                embedding = self.provider.generate_embedding(text=text, model=model)
                entry = self._build_entry(TTLPolicy.SLIDING, embedding, ttl_seconds, 0)
                self.store.set_entry(key, entry)
                self.metrics["misses"] += 1
                self.metrics["recomputes"] += 1
                return self._response(key, embedding, entry, source="computed", hit=False, recomputed=True, stale_served=False)

        if policy_enum == TTLPolicy.STALE_WHILE_REVALIDATE or entry.policy == TTLPolicy.STALE_WHILE_REVALIDATE:
            # Stale-while-revalidate
            created_age = now - entry.created_at
            fresh = entry.ttl_seconds if entry.ttl_seconds is not None else ttl_seconds
            stale = entry.stale_ttl_seconds if entry.stale_ttl_seconds is not None else stale_ttl_seconds
            within_fresh = created_age <= fresh
            within_stale = created_age <= fresh + stale

            # normalize policy fields to current request
            entry.policy = TTLPolicy.STALE_WHILE_REVALIDATE
            entry.ttl_seconds = fresh
            entry.stale_ttl_seconds = stale

            if within_fresh:
                entry.last_access = now
                self.store.set_entry(key, entry)
                self.metrics["hits"] += 1
                return self._response(key, entry.value, entry, source="cache", hit=True, recomputed=False, stale_served=False)
            elif within_stale:
                # serve stale, kick off background refresh
                entry.last_access = now
                self.store.set_entry(key, entry)
                self._start_background_refresh(key, text, model, fresh, stale)
                self.metrics["stale_served"] += 1
                return self._response(key, entry.value, entry, source="stale_cache", hit=True, recomputed=False, stale_served=True)
            else:
                # fully expired
                embedding = self.provider.generate_embedding(text=text, model=model)
                entry = self._build_entry(TTLPolicy.STALE_WHILE_REVALIDATE, embedding, fresh, stale)
                self.store.set_entry(key, entry)
                self.metrics["misses"] += 1
                self.metrics["recomputes"] += 1
                return self._response(key, embedding, entry, source="computed", hit=False, recomputed=True, stale_served=False)

        # Default fixed policy
        if entry.expires_at is not None and now <= entry.expires_at:
            entry.last_access = now
            entry.policy = TTLPolicy.FIXED
            self.store.set_entry(key, entry)
            self.metrics["hits"] += 1
            return self._response(key, entry.value, entry, source="cache", hit=True, recomputed=False, stale_served=False)
        else:
            embedding = self.provider.generate_embedding(text=text, model=model)
            entry = self._build_entry(TTLPolicy.FIXED, embedding, ttl_seconds, 0)
            self.store.set_entry(key, entry)
            self.metrics["misses"] += 1
            self.metrics["recomputes"] += 1
            return self._response(key, embedding, entry, source="computed", hit=False, recomputed=True, stale_served=False)

    def _build_entry(self, policy: TTLPolicy, value, ttl_seconds: int, stale_ttl_seconds: int):
        now = self._now()
        expires_at = None
        if policy == TTLPolicy.FIXED or policy == TTLPolicy.SLIDING:
            expires_at = now + int(ttl_seconds)
        elif policy == TTLPolicy.STALE_WHILE_REVALIDATE:
            expires_at = now + int(ttl_seconds)
        elif policy == TTLPolicy.FOREVER:
            expires_at = None
        return CacheEntry(
            value=value,
            policy=policy,
            created_at=now,
            last_access=now,
            expires_at=expires_at,
            ttl_seconds=int(ttl_seconds) if ttl_seconds is not None else None,
            stale_ttl_seconds=int(stale_ttl_seconds) if stale_ttl_seconds is not None else 0,
        )

    def _response(self, key, embedding, entry: CacheEntry, source: str, hit: bool, recomputed: bool, stale_served: bool):
        now = self._now()
        expires_at = entry.expires_at
        age_seconds = now - entry.created_at
        return {
            "key": key,
            "embedding": embedding,
            "cached": hit,
            "source": source,
            "policy": entry.policy.value,
            "expires_at": int(expires_at) if expires_at is not None else None,
            "age_seconds": age_seconds,
            "ttl_seconds": entry.ttl_seconds,
            "stale_ttl_seconds": entry.stale_ttl_seconds,
            "metrics": {
                "hit": hit,
                "recomputed": recomputed,
                "stale_served": stale_served,
            },
        }


app = Flask(__name__)

provider = EmbeddingProvider()
store = InMemoryCache()
cache = EmbeddingCache(provider, store)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "time": time.time()})


@app.route("/embed", methods=["POST"])
def embed():
    data = request.get_json(force=True)
    text = data.get("text")
    model = data.get("model", "fake-embedding-1")
    policy = data.get("policy", "fixed")
    ttl_seconds = int(data.get("ttl_seconds", os.getenv("EMBED_TTL_SECONDS", 86400)))
    stale_ttl_seconds = int(data.get("stale_ttl_seconds", os.getenv("EMBED_STALE_TTL_SECONDS", 43200)))
    force_refresh = bool(data.get("force_refresh", False))

    if not text or not isinstance(text, str):
        return jsonify({"error": "text is required"}), 400

    try:
        result = cache.embed(
            text=text,
            model=model,
            policy=policy,
            ttl_seconds=ttl_seconds,
            stale_ttl_seconds=stale_ttl_seconds,
            force_refresh=force_refresh,
        )
        # ensure embedding is JSON-friendly list of floats
        if hasattr(result.get("embedding"), "tolist"):
            result["embedding"] = result["embedding"].tolist()
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "detail": str(e)}), 500


@app.route("/stats", methods=["GET"])
def stats():
    store.purge_expired()
    data = {
        "cache_size": store.size(),
        "metrics": cache.metrics,
        "store": store.stats(),
        "time": time.time(),
    }
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/cache/stats', methods=['GET'])
def _auto_stub_cache_stats():
    return 'Auto-generated stub for /cache/stats', 200
