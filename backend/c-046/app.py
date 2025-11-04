import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, jsonify, request, make_response, render_template
from security.middleware import register_security_middleware
from security.csp_scanner import suggest_csp_policy_from_paths
from security.policy import CSPPolicyConfig, CORSConfig


def create_app():
    app = Flask(__name__)

    # Defaults
    app.config.setdefault("ENV", os.getenv("FLASK_ENV", "development"))
    app.config.setdefault("SECURITY", {})

    # Default CSP baseline
    default_csp = CSPPolicyConfig(
        default_src=["'self'"],
        script_src=["'self'"],
        style_src=["'self'"],
        img_src=["'self'", "data:"],
        font_src=["'self'", "data:"],
        connect_src=["'self'"],
        frame_src=["'self'"],
        object_src=["'none'"],
        base_uri=["'self'"],
        form_action=["'self'"],
        upgrade_insecure_requests=(app.config["ENV"] == "production"),
        block_all_mixed_content=False,
        report_uri=None,
        report_to=None,
    )

    default_cors = CORSConfig(
        mode="strict",
        allow_origins=[],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=[],
        allow_credentials=False,
        max_age=600,
    )

    app.config["SECURITY"]["CSP_POLICY"] = default_csp.to_dict()
    app.config["SECURITY"]["CORS"] = default_cors.to_dict()
    app.config["SECURITY"]["HEADERS"] = {
        "hsts": app.config["ENV"] == "production",
        "x_content_type_options": True,
        "x_frame_options": "DENY",  # or SAMEORIGIN
        "referrer_policy": "strict-origin-when-cross-origin",
        "permissions_policy": "geolocation=(), microphone=(), camera=(), payment=()",
        "coep": "require-corp",  # Cross-Origin-Embedder-Policy
        "coop": "same-origin",   # Cross-Origin-Opener-Policy
        "corp": "same-origin",   # Cross-Origin-Resource-Policy
    }

    # Register security middleware
    register_security_middleware(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    # --- CSP Suggestion Endpoint ---
    @app.get("/api/policy/csp/suggest")
    def csp_suggest():
        templates_dir = os.path.join(app.root_path, "templates")
        static_dir = os.path.join(app.root_path, "static")
        suggestions = suggest_csp_policy_from_paths([templates_dir, static_dir])

        # Merge suggestion with current configured policy (union)
        current = CSPPolicyConfig.from_dict(app.config["SECURITY"]["CSP_POLICY"]) if app.config["SECURITY"].get("CSP_POLICY") else CSPPolicyConfig()
        merged = current.merge(CSPPolicyConfig.from_dict(suggestions))
        return jsonify({
            "suggested": suggestions,
            "current": current.to_dict(),
            "merged": merged.to_dict(),
        })

    @app.post("/api/policy/csp/apply")
    def csp_apply():
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400
        try:
            new_policy = CSPPolicyConfig.from_dict(payload)
        except Exception as e:
            return jsonify({"error": f"Invalid CSP policy: {e}"}), 400
        app.config["SECURITY"]["CSP_POLICY"] = new_policy.to_dict()
        return jsonify({"ok": True, "applied": new_policy.to_dict()})

    # --- CORS Templates and Apply ---
    @app.get("/api/policy/cors/templates")
    def cors_templates():
        templates = {
            "strict": CORSConfig(mode="strict").to_dict(),
            "public": CORSConfig(mode="public").to_dict(),
            "dev": CORSConfig(
                mode="allowlist",
                allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
                expose_headers=[],
                allow_credentials=True,
                max_age=600,
            ).to_dict(),
            "allowlist_example": CORSConfig(
                mode="allowlist",
                allow_origins=["https://app.example.com", "https://admin.example.com"],
                allow_methods=["GET", "POST"],
                allow_headers=["Content-Type", "Authorization"],
                expose_headers=["X-Request-Id"],
                allow_credentials=True,
                max_age=86400,
            ).to_dict()
        }
        return jsonify(templates)

    @app.post("/api/policy/cors/apply")
    def cors_apply():
        try:
            payload = request.get_json(force=True)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400
        try:
            cfg = CORSConfig.from_dict(payload)
        except Exception as e:
            return jsonify({"error": f"Invalid CORS config: {e}"}), 400
        app.config["SECURITY"]["CORS"] = cfg.to_dict()
        return jsonify({"ok": True, "applied": cfg.to_dict()})

    @app.get("/api/policy/current")
    def policy_current():
        return jsonify(app.config.get("SECURITY", {}))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))



@app.route('/generate/csp', methods=['POST'])
def _auto_stub_generate_csp():
    return 'Auto-generated stub for /generate/csp', 200


@app.route('/generate/cors', methods=['POST'])
def _auto_stub_generate_cors():
    return 'Auto-generated stub for /generate/cors', 200
