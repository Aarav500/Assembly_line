import logging
import os

from .logging_config import setup_logging
from .tracing import setup_tracing, instrument_http_clients, instrument_flask
from .metrics import register_metrics

_INSTRUMENTED = False


def enable_auto_instrumentation(flask_app=None):
    global _INSTRUMENTED
    if _INSTRUMENTED:
        return

    # Logging first, so subsequent setup logs are structured
    if os.environ.get("LOGGING_ENABLED", "1").lower() not in ("0", "false"): 
        setup_logging()

    # Tracing
    if os.environ.get("TRACING_ENABLED", "1").lower() not in ("0", "false"):
        setup_tracing()
        instrument_http_clients()
        # Instrument Flask globally so any Flask app created later is traced
        try:
            instrument_flask(flask_app)
        except Exception:  # noqa: S110
            logging.getLogger(__name__).exception("Failed to instrument Flask")

    # Metrics
    if os.environ.get("METRICS_ENABLED", "1").lower() not in ("0", "false") and flask_app is not None:
        try:
            register_metrics(flask_app)
        except Exception:  # noqa: S110
            logging.getLogger(__name__).exception("Failed to register metrics")

    _INSTRUMENTED = True


def instrument_flask_app(app):
    """Convenience wrapper to instrument a Flask app (tracing + metrics)."""
    enable_auto_instrumentation(flask_app=app)

