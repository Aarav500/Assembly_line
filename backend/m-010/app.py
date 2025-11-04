import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from src.explain import generate_explanation

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/explain-change")
def explain_change():
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    message = payload.get("message")
    files = payload.get("files")
    diff = payload.get("diff")

    try:
        explanation = generate_explanation(message=message, files=files, diff=diff)
        return jsonify({"explanation": explanation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)



def create_app():
    return app


@app.route('/commits', methods=['GET', 'POST'])
def _auto_stub_commits():
    return 'Auto-generated stub for /commits', 200


@app.route('/commits/abc123', methods=['GET'])
def _auto_stub_commits_abc123():
    return 'Auto-generated stub for /commits/abc123', 200
