import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, render_template
from transpilers import transpile, supported_languages

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html', languages=supported_languages())


@app.route('/api/transpile', methods=['POST'])
def api_transpile():
    data = request.get_json(silent=True) or {}
    source = (data.get('source_language') or '').strip().lower()
    target = (data.get('target_language') or '').strip().lower()
    code = data.get('code') or ''

    if not source or not target:
        return jsonify({
            'output': '',
            'warnings': [],
            'errors': ['Both source_language and target_language are required.']
        }), 400

    try:
        output, warnings = transpile(source, target, code)
        return jsonify({'output': output, 'warnings': warnings, 'errors': []})
    except ValueError as ve:
        return jsonify({'output': '', 'warnings': [], 'errors': [str(ve)]}), 400
    except Exception as e:
        return jsonify({'output': '', 'warnings': [], 'errors': ['Internal error: ' + str(e)]}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
