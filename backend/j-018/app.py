import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, render_template, request, jsonify
import requests
from accessibility.analyzer import analyze_html


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/analyze")
    def analyze():
        try:
            data = request.get_json(force=True, silent=True) or {}
            html = data.get("html", "")
            url = data.get("url")

            if url and not html:
                try:
                    resp = requests.get(url, timeout=10)
                    resp.raise_for_status()
                    html = resp.text
                except Exception as e:
                    return jsonify({
                        "ok": False,
                        "error": f"Failed to fetch URL: {e}"
                    }), 400

            if not html:
                return jsonify({"ok": False, "error": "No HTML provided"}), 400

            result = analyze_html(html, base_url=url)
            return jsonify({"ok": True, "result": result})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/api/check', methods=['POST'])
def _auto_stub_api_check():
    return 'Auto-generated stub for /api/check', 200
