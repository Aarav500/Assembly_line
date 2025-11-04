import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

from log_parser import parse_text, parse_file
from storage import add_runs, aggregate_tests, ensure_data_dirs
from test_generator import generate_tests_for_flaky

app = Flask(__name__, static_folder="static")

ensure_data_dirs()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + 'Z'})

@app.route('/api/logs', methods=['POST'])
def upload_logs():
    parsed_all = []
    meta = {
        "parsed": 0,
        "stored": 0,
        "sources": []
    }

    # Handle multipart file uploads
    if request.files:
        files = request.files.getlist('file')
        for f in files:
            filename = secure_filename(f.filename)
            source = filename or 'upload'
            try:
                content = f.read().decode('utf-8', errors='ignore')
            except Exception:
                content = f.read().decode('latin-1', errors='ignore')
            runs = parse_text(content, source=source)
            parsed_all.extend(runs)
            meta["sources"].append(source)

    # Handle raw text in JSON or form
    elif request.is_json and (request.json.get('text') or request.json.get('path')):
        body = request.json
        if body.get('text'):
            runs = parse_text(body['text'], source=body.get('source', 'inline'))
            parsed_all.extend(runs)
            meta["sources"].append(body.get('source', 'inline'))
        if body.get('path'):
            root = body['path']
            exts = tuple(body.get('extensions', ['.log', '.txt']))
            if not os.path.exists(root):
                return jsonify({"error": f"path does not exist: {root}"}), 400
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    if not name.lower().endswith(exts):
                        continue
                    filepath = os.path.join(dirpath, name)
                    try:
                        runs = parse_file(filepath)
                        parsed_all.extend(runs)
                        meta["sources"].append(filepath)
                    except Exception as e:
                        # Skip unreadable files
                        continue
    else:
        return jsonify({"error": "No logs provided. Use multipart 'file' or JSON with 'text' or 'path'."}), 400

    meta['parsed'] = len(parsed_all)
    if parsed_all:
        stored = add_runs(parsed_all)
        meta['stored'] = stored

    return jsonify(meta)

@app.route('/api/tests', methods=['GET'])
def list_tests():
    agg = aggregate_tests()
    items = []
    for name, data in agg.items():
        items.append({
            "test_name": name,
            "counts": data['counts'],
            "statuses": sorted(list(data['statuses'])),
            "runs": len(data['runs'])
        })
    items.sort(key=lambda x: (-x['counts'].get('FAIL', 0), -x['counts'].get('ERROR', 0), x['test_name']))
    return jsonify({"tests": items})

@app.route('/api/tests/flaky', methods=['GET'])
def list_flaky():
    agg = aggregate_tests()
    flaky = []
    for name, data in agg.items():
        statuses = data['statuses']
        if 'PASS' in statuses and ('FAIL' in statuses or 'ERROR' in statuses):
            flaky.append({
                "test_name": name,
                "counts": data['counts'],
                "runs": len(data['runs'])
            })
    flaky.sort(key=lambda x: (-x['counts'].get('FAIL', 0), -x['counts'].get('ERROR', 0), x['test_name']))
    return jsonify({"flaky": flaky})

@app.route('/api/generate', methods=['POST'])
def generate():
    body = request.json or {}
    output_dir = body.get('output_dir', 'generated_tests')
    limit = body.get('limit')
    results = generate_tests_for_flaky(output_dir=output_dir, limit=limit)
    return jsonify(results)

@app.route('/', methods=['GET'])
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



def create_app():
    return app


@app.route('/api/flaky-tests', methods=['GET'])
def _auto_stub_api_flaky_tests():
    return 'Auto-generated stub for /api/flaky-tests', 200
