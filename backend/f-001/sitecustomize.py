# This module is imported automatically by Python if present on sys.path
# It enables auto-instrumentation (tracing/logging) without changing app code.
import os

try:
    if os.environ.get("AUTO_INSTRUMENT", "1").lower() not in ("0", "false"):  # opt-out
        from instrumentation.auto_instrument import enable_auto_instrumentation
        # We cannot attach metrics endpoint without the Flask app instance here, but
        # tracing/logging and global Flask instrumentation are activated.
        enable_auto_instrumentation(flask_app=None)
except Exception:
    # Never break application startup because of instrumentation failures
    pass

