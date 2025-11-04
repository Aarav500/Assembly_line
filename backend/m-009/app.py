import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request, render_template
from datetime import datetime


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object("config.Config")

    from scheduler import init_scheduler
    init_scheduler(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"})

    @app.route("/digest/preview")
    def digest_preview():
        from digest import build_digest
        data = build_digest(app.config)
        fmt = request.args.get("format", "json")
        if fmt == "html":
            return render_template("email_digest.html", **data)
        elif fmt == "text":
            return render_template("email_digest.txt", **data)
        else:
            return jsonify(data)

    @app.route("/digest/send", methods=["POST", "GET"])  # allow GET for convenience
    def digest_send():
        from digest import build_digest
        from emailer import send_digest_to_owners
        data = build_digest(app.config)
        to_param = request.args.get("to") or request.form.get("to")
        recipients = [e.strip() for e in (to_param.split(",") if to_param else []) if e.strip()]
        result = send_digest_to_owners(app, data, recipients if recipients else None)
        return jsonify(result), (200 if result.get("ok") else 500)

    return app


if __name__ == "__main__":
    # For local debugging
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

