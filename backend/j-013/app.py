import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
import zipfile
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from config import Config
import figma_client
import code_parser
import inspector

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Ensure storage directories exist
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, 'storage')
UPLOADS_DIR = os.path.join(STORAGE_DIR, 'uploads')
CODE_DIR = os.path.join(STORAGE_DIR, 'code')
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(CODE_DIR, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"})

@app.route('/api/upload-code', methods=['POST'])
def upload_code():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded. Use multipart form with field 'file' containing a zip of your codebase."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename."}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.zip'):
        return jsonify({"error": "Only .zip archives are supported."}), 400

    code_id = str(uuid.uuid4())
    dest_zip_path = os.path.join(UPLOADS_DIR, f"{code_id}.zip")
    file.save(dest_zip_path)

    extract_dir = os.path.join(CODE_DIR, code_id)
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(dest_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid zip file."}), 400

    tokens = code_parser.extract_code_tokens(extract_dir)

    tokens_path = os.path.join(extract_dir, 'tokens_parsed.json')
    with open(tokens_path, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, indent=2)

    stats = {
        'colors': len(tokens.get('colors', [])),
        'textStyles': len(tokens.get('textStyles', [])),
    }

    return jsonify({"code_id": code_id, "stats": stats})

@app.route('/api/figma/styles', methods=['GET'])
def figma_styles():
    file_key = request.args.get('file_key')
    if not file_key:
        return jsonify({"error": "Missing query param 'file_key'"}), 400

    try:
        file_json = figma_client.get_file(file_key)
        tokens = figma_client.extract_style_values(file_json)
    except figma_client.FigmaAPIError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(tokens)

@app.route('/api/inspect', methods=['POST'])
def inspect_roundtrip():
    data = request.get_json(silent=True) or request.form
    figma_file_key = data.get('figma_file_key')
    code_id = data.get('code_id')

    if not figma_file_key:
        return jsonify({"error": "Missing figma_file_key"}), 400
    if not code_id:
        return jsonify({"error": "Missing code_id. Upload code zip via /api/upload-code first."}), 400

    code_path = os.path.join(CODE_DIR, code_id)
    tokens_path = os.path.join(code_path, 'tokens_parsed.json')
    if not os.path.isdir(code_path) or not os.path.isfile(tokens_path):
        return jsonify({"error": "Unknown code_id or tokens not parsed."}), 404

    try:
        file_json = figma_client.get_file(figma_file_key)
        figma_tokens = figma_client.extract_style_values(file_json)
    except figma_client.FigmaAPIError as e:
        return jsonify({"error": str(e)}), 400

    with open(tokens_path, 'r', encoding='utf-8') as f:
        code_tokens = json.load(f)

    report = inspector.generate_report(figma_tokens, code_tokens)
    return jsonify(report)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static'), filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/generate-code', methods=['POST'])
def _auto_stub_generate_code():
    return 'Auto-generated stub for /generate-code', 200


@app.route('/compare', methods=['POST'])
def _auto_stub_compare():
    return 'Auto-generated stub for /compare', 200
