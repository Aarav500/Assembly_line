import logging
from functools import wraps
from typing import Callable

from flask import request

from config import Config
from context import get_request_id, get_correlation_id
from utils.sanitization import sanitize_sentry_event

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
except Exception:  # pragma: no cover - optional dependency
    sentry_sdk = None
    FlaskIntegration = None

logger = logging.getLogger("app.sentry")


def init_sentry(app, config: Config) -> None:
    if not config.SENTRY_ENABLED or not config.SENTRY_DSN or not sentry_sdk:
        logger.info("Sentry disabled or not configured")
        return

    def before_send(event, hint):
        return sanitize_sentry_event(event, hint, redacted_keys=config.LOG_REDACT_FIELDS)

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.SENTRY_ENVIRONMENT,
        release=config.SENTRY_RELEASE,
        integrations=[FlaskIntegration()],
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        before_send=before_send,
        send_default_pii=False,
    )

    logger.info("Sentry initialized")


def bind_request_context_to_sentry(fn: Callable):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if sentry_sdk:
            with sentry_sdk.configure_scope() as scope:  # type: ignore[attr-defined]
                # Attach request-scoped ids as tags
                rid = get_request_id()
                cid = get_correlation_id()
                if rid:
                    scope.set_tag("request_id", rid)
                if cid:
                    scope.set_tag("correlation_id", cid)
                # Avoid leaking sensitive headers
                scope.set_context(
                    "http.request.minimal",
                    {
                        "method": request.method,
                        "path": request.path,
                        "query_string": request.query_string.decode("utf-8", errors="ignore")[:512],
                    },
                )
        return fn(*args, **kwargs)

    return wrapper

