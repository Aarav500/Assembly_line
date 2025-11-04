import os
from flask import Flask, request, g
from .config import Config
from .feature_flags import FeatureFlagStore

def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config_object or Config)

    # Feature flag store
    store = FeatureFlagStore(app.config["FEATURE_FLAG_FILE"])
    store.load()
    app.extensions["feature_flags"] = store

    @app.before_request
    def parse_flag_overrides():
        # Allow per-request overrides via header: X-Flag-Override: flag_a=on,flag_b=off
        header = request.headers.get("X-Flag-Override")
        overrides = {}
        if header:
            parts = [p.strip() for p in header.split(",") if p.strip()]
            for part in parts:
                if "=" in part:
                    name, value = part.split("=", 1)
                    name = name.strip()
                    value = value.strip().lower()
                    if value in {"1", "true", "on", "yes"}:
                        overrides[name] = True
                    elif value in {"0", "false", "off", "no"}:
                        overrides[name] = False
        g.flag_overrides = overrides

    @app.context_processor
    def inject_flag_helpers():
        def flag_enabled(name, default=False):
            return store.is_enabled(name, default=default, overrides=getattr(g, "flag_overrides", None))
        return {"flag_enabled": flag_enabled}

    # Blueprints
    from .blueprints.flags import bp as flags_bp
    app.register_blueprint(flags_bp)

    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app

