import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import os
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from services.figma_service import extract_tokens_from_figma
from services.sketch_service import extract_tokens_from_sketch
from services.tokens import build_css_from_tokens, normalize_tokens

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"})


@app.post('/api/figma/export')
def api_figma_export():
    try:
        data = request.get_json(silent=True) or {}
        file_key = data.get('file_key') or request.args.get('file_key')
        token = data.get('token') or os.getenv('FIGMA_TOKEN')
        name_prefix = data.get('prefix', '')
        if not file_key:
            return jsonify({"error": "Missing file_key"}), 400
        if not token:
            return jsonify({"error": "Missing token (provide in body.token or FIGMA_TOKEN env)"}), 400
        raw_tokens, meta = extract_tokens_from_figma(file_key=file_key, token=token)
        tokens = normalize_tokens(raw_tokens, prefix=name_prefix)
        css_vars, css_utils = build_css_from_tokens(tokens)
        return jsonify({
            "source": {
                "type": "figma",
                "file_key": file_key,
                "meta": meta
            },
            "tokens": tokens,
            "css": {
                "variables": css_vars,
                "utilities": css_utils
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post('/api/sketch/export')
def api_sketch_export():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        file = request.files['file']
        if not file.filename.lower().endswith('.sketch'):
            return jsonify({"error": "Only .sketch files are supported"}), 400
        prefix = request.form.get('prefix', '')
        file_bytes = file.read()
        raw_tokens, meta = extract_tokens_from_sketch(io.BytesIO(file_bytes), filename=secure_filename(file.filename))
        tokens = normalize_tokens(raw_tokens, prefix=prefix)
        css_vars, css_utils = build_css_from_tokens(tokens)
        return jsonify({
            "source": {
                "type": "sketch",
                "filename": file.filename,
                "meta": meta
            },
            "tokens": tokens,
            "css": {
                "variables": css_vars,
                "utilities": css_utils
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=True)



def create_app():
    return app


@app.route('/export/css', methods=['GET'])
def _auto_stub_export_css():
    return 'Auto-generated stub for /export/css', 200


@app.route('/export/figma', methods=['GET'])
def _auto_stub_export_figma():
    return 'Auto-generated stub for /export/figma', 200


@app.route('/export/sketch', methods=['GET'])
def _auto_stub_export_sketch():
    return 'Auto-generated stub for /export/sketch', 200


@app.route('/tokens', methods=['GET'])
def _auto_stub_tokens():
    return 'Auto-generated stub for /tokens', 200
