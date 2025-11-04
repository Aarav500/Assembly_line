import os
import sys

import debugpy  # type: ignore
from app import create_app


def maybe_enable_debugpy():
    # Enable debugpy if requested (useful in devcontainers)
    enabled = os.getenv("ENABLE_DEBUGPY", "0")
    if enabled not in ("1", "true", "True"):  # default disabled
        return
    try:
        port = int(os.getenv("DEBUGPY_PORT", "5678"))
        debugpy.listen(("0.0.0.0", port))
        # Wait for debugger to attach if requested
        if os.getenv("DEBUGPY_WAIT_FOR_CLIENT", "0") in ("1", "true", "True"):
            print(f"Waiting for debugpy client to attach on port {port}...", flush=True)
            debugpy.wait_for_client()
    except Exception as e:  # pragma: no cover - best effort
        print(f"Failed to enable debugpy: {e}", file=sys.stderr)


if __name__ == "__main__":
    maybe_enable_debugpy()
    app = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)

