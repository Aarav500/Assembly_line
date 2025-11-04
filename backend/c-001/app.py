import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, abort
from dotenv import load_dotenv

from llm import LLMClient
from file_writer import write_files_to_directory, validate_files_schema, summarize_files
from utils.archive import zip_directory

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

BASE_OUTPUT_DIR = Path(os.environ.get('OUTPUT_BASE', 'generated')).resolve()
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES = int(os.environ.get('MAX_FILES', '200'))
MAX_TOTAL_BYTES = int(os.environ.get('MAX_TOTAL_BYTES', str(5 * 1024 * 1024)))  # 5MB default

SYSTEM_PROMPT_PATH = Path('prompts/system_prompt.txt')
DEFAULT_SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8') if SYSTEM_PROMPT_PATH.exists() else 'You are a code generator.'


def slugify(value: str) -> str:
    s = ''.join(c if c.isalnum() or c in ('-', '_') else '-' for c in value.strip())
    s = '-'.join(filter(None, s.split('-')))
    return s[:64] or 'repo'


def make_repo_id(name: str) -> str:
    ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    uid = uuid.uuid4().hex[:6]
    return f"{ts}-{slugify(name)}-{uid}"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"})


@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json(force=True, silent=True) or {}
    user_prompt = data.get('prompt', '').strip()
    repo_name = data.get('repo_name', 'my-generated-repo').strip() or 'my-generated-repo'
    model = data.get('model') or os.environ.get('OPENAI_MODEL') or 'gpt-4o-mini'
    force_fake = bool(data.get('fake')) if 'fake' in data else (os.environ.get('LLM_FAKE', 'false').lower() == 'true')

    if not user_prompt:
        return jsonify({"error": "Missing prompt"}), 400

    repo_id = make_repo_id(repo_name)
    repo_dir = BASE_OUTPUT_DIR / repo_id
    repo_dir.mkdir(parents=True, exist_ok=True)

    client = LLMClient(model=model, force_fake=force_fake)

    try:
        files_payload = client.generate_repo_files(system_prompt=DEFAULT_SYSTEM_PROMPT, user_prompt=user_prompt)
    except Exception as e:
        return jsonify({"error": f"LLM call failed: {e}"}), 500

    try:
        validate_files_schema(files_payload, max_files=MAX_FILES, max_total_bytes=MAX_TOTAL_BYTES)
    except ValueError as ve:
        # Clean up empty repo dir
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
        return jsonify({"error": str(ve)}), 400

    try:
        write_files_to_directory(repo_dir, files_payload['files'])
    except Exception as e:
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
        return jsonify({"error": f"Failed to write files: {e}"}), 500

    # Create zip
    zip_path = BASE_OUTPUT_DIR / f"{repo_id}.zip"
    try:
        zip_directory(repo_dir, zip_path)
    except Exception as e:
        return jsonify({"error": f"Failed to archive repo: {e}"}), 500

    summary = summarize_files(files_payload['files'])
    return jsonify({
        "id": repo_id,
        "repo_name": repo_name,
        "dir": str(repo_dir.relative_to(Path.cwd())),
        "zip_url": f"/download/{repo_id}.zip",
        "files": summary
    })


@app.route('/download/<repo_zip>')
def download(repo_zip: str):
    # expects <id>.zip
    if not repo_zip.endswith('.zip'):
        abort(404)
    full = BASE_OUTPUT_DIR / repo_zip
    if not full.exists() or not full.is_file():
        abort(404)
    return send_from_directory(BASE_OUTPUT_DIR, repo_zip, as_attachment=True)


@app.route('/repo/<repo_id>/<path:filepath>')
def get_file(repo_id: str, filepath: str):
    base = BASE_OUTPUT_DIR / repo_id
    if not base.exists():
        abort(404)
    # Prevent path traversal by resolving
    requested = (base / filepath).resolve()
    try:
        requested.relative_to(base)
    except Exception:
        abort(400)
    if not requested.exists() or not requested.is_file():
        abort(404)
    return send_from_directory(base, str(Path(filepath)), as_attachment=False)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000'))) 



def create_app():
    return app


@app.route('/api/data', methods=['GET'])
def _auto_stub_api_data():
    return 'Auto-generated stub for /api/data', 200
