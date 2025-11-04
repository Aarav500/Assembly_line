import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from datetime import datetime
from roadmap_generator.generator import validate_and_normalize_input, generate_roadmap


def create_app():
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/api/health')
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + 'Z'})

    @app.route('/api/generate-roadmap', methods=['POST'])
    def api_generate_roadmap():
        try:
            payload = request.get_json(silent=True) or {}
            params = validate_and_normalize_input(payload)
            roadmap = generate_roadmap(params)
            return jsonify(roadmap)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



@app.route('/api/roadmap', methods=['POST'])
def _auto_stub_api_roadmap():
    return 'Auto-generated stub for /api/roadmap', 200


@app.route('/api/milestone/1', methods=['GET'])
def _auto_stub_api_milestone_1():
    return 'Auto-generated stub for /api/milestone/1', 200
