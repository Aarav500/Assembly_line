import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request, abort
from feature_flags import EnvKV, FileKV, CompositeKV, FeatureFlags, flag_required, register_flask


def create_app():
    app = Flask(__name__)

    # Configure KV backends
    env_prefix = os.getenv("FEATURE_FLAGS_ENV_PREFIX", "FF_")
    flags_file = os.getenv("FEATURE_FLAGS_FILE", os.path.join(os.path.dirname(__file__), "flags.json"))
    missing_default = os.getenv("FEATURE_FLAG_DEFAULT", "false").lower() in ("1", "true", "yes", "on")

    env_kv = EnvKV(prefix=env_prefix)
    file_kv = FileKV(flags_file)

    # Precedence: Environment overrides File
    kv = CompositeKV([env_kv, file_kv])
    flags = FeatureFlags(kv, default_enabled=missing_default)

    register_flask(app, flags)

    @app.get("/")
    def index():
        return jsonify({
            "message": "Feature Flags Demo",
            "flags": flags.all()
        })

    @app.get("/beta")
    @flag_required("beta_endpoint", default=False, unauthorized_status=404)
    def beta_only():
        return jsonify({"ok": True, "message": "Welcome to the beta endpoint!"})

    @app.get("/search")
    def search():
        if flags.enabled("search_v2", default=False):
            # New implementation
            return jsonify({"version": "v2", "results": ["alpha", "bravo", "charlie"]})
        else:
            # Legacy implementation
            return jsonify({"version": "v1", "results": ["a", "b", "c"]})

    # Optional admin endpoints for deployment-time management of file-based flags
    if os.getenv("ENABLE_FLAG_ADMIN", "false").lower() in ("1", "true", "yes", "on"):
        admin_token = os.getenv("FLAG_ADMIN_TOKEN", "")

        def require_admin():
            if not admin_token:
                return
            token = request.headers.get("X-Admin-Token")
            if token != admin_token:
                abort(403)

        @app.get("/admin/flags")
        def admin_list_flags():
            require_admin()
            return jsonify({"flags": flags.all(), "source": "env_overrides_file"})

        @app.put("/admin/flags/<name>")
        def admin_set_flag(name):
            require_admin()
            payload = request.get_json(silent=True) or {}
            if "value" not in payload:
                return jsonify({"error": "Missing 'value' in body"}), 400
            # Persist to FileKV if available
            writable = None
            for backend in getattr(kv, "backends", []):
                if hasattr(backend, "set"):
                    writable = backend
                    break
            if not writable or not isinstance(writable, FileKV):
                return jsonify({"error": "Writable file-based KV backend not configured"}), 400
            writable.set(name, payload["value"])
            return jsonify({"ok": True, "name": name, "value": payload["value"]})

    return app


if __name__ == "__main__":
    app = create_app()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    app.run(host=host, port=port)



@app.route('/feature/new_ui', methods=['GET'])
def _auto_stub_feature_new_ui():
    return 'Auto-generated stub for /feature/new_ui', 200
