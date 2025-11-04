import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from src.scope_suggester import suggest_scope, sample_payload


def create_app():
    app = Flask(__name__)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/sample', methods=['GET'])
    def api_sample():
        return jsonify(sample_payload())

    @app.route('/api/suggest', methods=['POST'])
    def api_suggest():
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception as e:
            return jsonify({"error": f"Invalid JSON: {e}"}), 400
        try:
            result = suggest_scope(payload)
            return jsonify(result)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Server error: {e}"}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/features', methods=['GET'])
def _auto_stub_features():
    return 'Auto-generated stub for /features', 200


@app.route('/suggest-mvp', methods=['POST'])
def _auto_stub_suggest_mvp():
    return 'Auto-generated stub for /suggest-mvp', 200
