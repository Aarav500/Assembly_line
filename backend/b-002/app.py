import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from datetime import datetime
import os

from generator import generate_plan


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/generate")
    def api_generate():
        try:
            data = request.get_json(force=True, silent=True) or {}
            one_liner = (data.get("one_liner") or "").strip()
            tone = (data.get("tone") or "professional").strip().lower()
            if not one_liner:
                return jsonify({"error": "one_liner is required"}), 400
            result = generate_plan(one_liner, tone=tone)
            return jsonify({
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "input": {"one_liner": one_liner, "tone": tone},
                "plan": result
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

