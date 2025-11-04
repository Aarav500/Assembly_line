import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from generator import generate_experiment_design

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def api_generate():
    try:
        payload = request.get_json(force=True)
        result = generate_experiment_design(payload or {})
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/generate/hypothesis', methods=['POST'])
def _auto_stub_generate_hypothesis():
    return 'Auto-generated stub for /generate/hypothesis', 200


@app.route('/generate/dataset?count=2', methods=['GET'])
def _auto_stub_generate_dataset_count_2():
    return 'Auto-generated stub for /generate/dataset?count=2', 200


@app.route('/generate/metrics?count=3', methods=['GET'])
def _auto_stub_generate_metrics_count_3():
    return 'Auto-generated stub for /generate/metrics?count=3', 200


@app.route('/generate/experiment', methods=['POST'])
def _auto_stub_generate_experiment():
    return 'Auto-generated stub for /generate/experiment', 200
