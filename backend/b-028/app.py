import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from generator.task_generator import TaskGenerator

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')

tg = TaskGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400

    idea = (data or {}).get('idea', '')
    context = (data or {}).get('context', '')

    if not idea or not isinstance(idea, str) or not idea.strip():
        return jsonify({"error": "'idea' is required and must be a non-empty string."}), 400

    result = tg.generate(idea=idea.strip(), context=(context or '').strip())
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/generate-tasks', methods=['POST'])
def _auto_stub_generate_tasks():
    return 'Auto-generated stub for /generate-tasks', 200
