from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from . import config
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .db import session_scope
from .repository import get_user_by_id, list_users
from .retry import call_with_retry

logger = logging.getLogger(__name__)

# Global circuit breaker for DB operations
breaker = CircuitBreaker(
    "db",
    CircuitBreakerConfig(
        failure_threshold=config.CIRCUIT_FAILURE_THRESHOLD,
        recovery_timeout=config.CIRCUIT_RECOVERY_TIMEOUT,
        half_open_max_success=config.CIRCUIT_HALF_OPEN_MAX_SUCCESS,
    ),
)

# Simple in-memory cache for graceful degradation
_cache_lock = threading.Lock()
_user_cache: dict[int, Dict[str, Any]] = {}


def _cache_put_user(user: Dict[str, Any]) -> None:
    with _cache_lock:
        _user_cache[user["id"]] = user


def _cache_get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        return _user_cache.get(user_id)


def _on_breaker_open(name: str) -> None:
    logger.error("Circuit breaker '%s' is OPEN; serving degraded response", name)


def _wrap_read_op(op):
    # Wrap a DB operation inside session and retry
    def call():
        with session_scope() as s:
            return op(s)
    return lambda: call_with_retry(
        call,
        max_attempts=config.RETRY_MAX_ATTEMPTS,
        base_delay=config.RETRY_BASE_DELAY,
        max_delay=config.RETRY_MAX_DELAY,
        logger=logger,
    )


def get_user_safe(user_id: int) -> Dict[str, Any]:
    def op(session):
        user = get_user_by_id(session, user_id)
        if not user:
            return {"status": "ok", "user": None}
        user_dict = user.to_dict()
        _cache_put_user(user_dict)
        return {"status": "ok", "user": user_dict}

    def fallback():
        cached = _cache_get_user(user_id)
        return {"status": "degraded", "user": cached}

    return breaker.execute(
        _wrap_read_op(op),
        fallback=fallback,
        on_open=_on_breaker_open,
    )


def list_users_safe(limit: int = 10) -> Dict[str, Any]:
    def op(session):
        users = [u.to_dict() for u in list_users(session, limit=limit)]
        for u in users:
            _cache_put_user(u)
        return {"status": "ok", "users": users}

    def fallback():
        with _cache_lock:
            # Return any cached users up to limit
            users = list(_user_cache.values())[:limit]
        return {"status": "degraded", "users": users}

    return breaker.execute(
        _wrap_read_op(op),
        fallback=fallback,
        on_open=_on_breaker_open,
    )

