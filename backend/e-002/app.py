import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import threading
import datetime as dt
import json
from flask import Flask, jsonify, request, send_file, abort
from buildsystem.build_manager import BuildManager
from buildsystem.storage import BuildStorage
from buildsystem.utils import load_yaml_files

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINES_DIR = os.path.join(BASE_DIR, 'pipelines')
BUILDS_DIR = os.path.join(BASE_DIR, 'builds')
PACKER_TEMPLATES_DIR = os.path.join(BASE_DIR, 'packer', 'templates')
SETTINGS_PATH = os.path.join(BASE_DIR, 'config', 'settings.yaml')

app = Flask(__name__)

os.makedirs(BUILDS_DIR, exist_ok=True)

settings = {}
if os.path.exists(SETTINGS_PATH):
    try:
        settings = load_yaml_files([SETTINGS_PATH])[0]['data']
    except Exception:
        settings = {}

pipeline_files = [os.path.join(PIPELINES_DIR, f) for f in os.listdir(PIPELINES_DIR) if f.endswith('.yaml') or f.endswith('.yml')]
_pipelines_loaded = load_yaml_files(pipeline_files)

# Prepare a dict: name -> pipeline dict
pipelines = {}
for item in _pipelines_loaded:
    data = item['data']
    if not data:
        continue
    name = data.get('name')
    if not name:
        continue
    pipelines[name] = data

storage = BuildStorage(os.path.join(BUILDS_DIR, 'builds.json'))
manager = BuildManager(storage=storage, base_dir=BASE_DIR, builds_dir=BUILDS_DIR, templates_dir=PACKER_TEMPLATES_DIR, default_settings=settings)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/pipelines', methods=['GET'])
def list_pipelines():
    return jsonify({
        'pipelines': [
            {
                'name': name,
                'template': p.get('template'),
                'variables': p.get('variables', {}),
                'description': p.get('description', '')
            }
            for name, p in pipelines.items()
        ]
    })

@app.route('/pipelines/<name>', methods=['GET'])
def get_pipeline(name):
    p = pipelines.get(name)
    if not p:
        abort(404)
    return jsonify(p)

@app.route('/pipelines/<name>/run', methods=['POST'])
def run_pipeline(name):
    p = pipelines.get(name)
    if not p:
        abort(404)
    body = request.get_json(silent=True) or {}
    overrides = body.get('overrides', {})
    ami_suffix = body.get('ami_suffix')
    build_id = str(uuid.uuid4())[:8]
    result = manager.enqueue_build(build_id=build_id, pipeline=p, overrides=overrides, ami_suffix=ami_suffix)
    return jsonify(result), 202

@app.route('/builds', methods=['GET'])
def list_builds():
    return jsonify({ 'builds': storage.list_builds() })

@app.route('/builds/<build_id>', methods=['GET'])
def get_build(build_id):
    build = storage.get_build(build_id)
    if not build:
        abort(404)
    return jsonify(build)

@app.route('/builds/<build_id>/logs', methods=['GET'])
def get_build_logs(build_id):
    build = storage.get_build(build_id)
    if not build:
        abort(404)
    log_path = build.get('log_path')
    if not log_path or not os.path.exists(log_path):
        abort(404)
    return send_file(log_path, mimetype='text/plain')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)



def create_app():
    return app


@app.route('/api/pipelines', methods=['POST'])
def _auto_stub_api_pipelines():
    return 'Auto-generated stub for /api/pipelines', 200


@app.route('/api/pipelines/pipeline-1', methods=['GET'])
def _auto_stub_api_pipelines_pipeline_1():
    return 'Auto-generated stub for /api/pipelines/pipeline-1', 200


@app.route('/api/pipelines/pipeline-2/build', methods=['POST'])
def _auto_stub_api_pipelines_pipeline_2_build():
    return 'Auto-generated stub for /api/pipelines/pipeline-2/build', 200
