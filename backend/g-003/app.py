import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
import zipfile
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

from config import SETTINGS
from utils.dataset_manager import DatasetManager
from utils.job_manager import JobManager
from training.runner import TrainingRunner

app = Flask(__name__)

datasets = DatasetManager(base_dir=SETTINGS['DATASETS_DIR'])
jobs = JobManager(state_path=os.path.join(SETTINGS['LOGS_DIR'], 'jobs_state.json'))
runner = TrainingRunner(job_manager=jobs, datasets=datasets, base_output_dir=SETTINGS['OUTPUTS_DIR'], logs_dir=SETTINGS['LOGS_DIR'])


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + 'Z'})


@app.route('/datasets', methods=['GET'])
def list_datasets():
    return jsonify(datasets.list_datasets())


@app.route('/datasets', methods=['POST'])
def create_dataset():
    if 'name' not in request.form:
        return jsonify({"error": "Missing 'name' in form data"}), 400
    name = request.form['name']
    metadata = request.form.get('metadata')
    try:
        metadata_obj = json.loads(metadata) if metadata else {}
    except Exception:
        return jsonify({"error": "Invalid metadata JSON"}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "No files uploaded. Use multipart/form-data with key 'files'"}), 400
    saved_files = []
    for f in files:
        filename = secure_filename(f.filename)
        saved_files.append((filename, f.stream.read()))

    try:
        version_info = datasets.create_dataset_version(name=name, files=saved_files, metadata=metadata_obj)
        return jsonify(version_info), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/datasets/<name>', methods=['GET'])
def get_dataset_info(name):
    info = datasets.get_dataset_info(name)
    if not info:
        return jsonify({"error": "Dataset not found"}), 404
    return jsonify(info)


@app.route('/datasets/<name>/versions', methods=['POST'])
def create_dataset_version(name):
    if not datasets.dataset_exists(name):
        return jsonify({"error": "Dataset does not exist. Create it via POST /datasets"}), 404
    metadata = request.form.get('metadata')
    try:
        metadata_obj = json.loads(metadata) if metadata else {}
    except Exception:
        return jsonify({"error": "Invalid metadata JSON"}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({"error": "No files uploaded. Use multipart/form-data with key 'files'"}), 400

    saved_files = []
    for f in files:
        filename = secure_filename(f.filename)
        saved_files.append((filename, f.stream.read()))

    try:
        version_info = datasets.create_dataset_version(name=name, files=saved_files, metadata=metadata_obj)
        return jsonify(version_info), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/datasets/<name>/versions/<version>', methods=['GET'])
def get_dataset_version(name, version):
    info = datasets.get_dataset_version_info(name, version)
    if not info:
        return jsonify({"error": "Dataset or version not found"}), 404
    return jsonify(info)


@app.route('/datasets/<name>/versions/<version>/download', methods=['GET'])
def download_dataset_version(name, version):
    version_path = datasets.get_version_path(name, version)
    if not version_path or not os.path.isdir(version_path):
        return jsonify({"error": "Dataset or version not found"}), 404
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(version_path):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, version_path)
                zf.write(fp, arcname)
    mem_zip.seek(0)
    return send_file(mem_zip, mimetype='application/zip', as_attachment=True, download_name=f'{name}_{version}.zip')


@app.route('/train', methods=['POST'])
def start_training():
    try:
        req = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    required = ['model_name', 'dataset_name']
    for k in required:
        if k not in req:
            return jsonify({"error": f"Missing required field: {k}"}), 400

    dataset_version = req.get('dataset_version', 'latest')
    if dataset_version == 'latest':
        latest = datasets.get_latest_version(req['dataset_name'])
        if not latest:
            return jsonify({"error": "Dataset not found or has no versions"}), 404
        dataset_version = latest

    dataset_path = datasets.get_version_path(req['dataset_name'], dataset_version)
    if not dataset_path:
        return jsonify({"error": "Dataset or version not found"}), 404

    train_config = {
        'model_name': req['model_name'],
        'dataset_name': req['dataset_name'],
        'dataset_version': dataset_version,
        'dataset_path': dataset_path,
        'num_train_epochs': float(req.get('num_train_epochs', 1.0)),
        'learning_rate': float(req.get('learning_rate', 2e-5)),
        'per_device_train_batch_size': int(req.get('per_device_train_batch_size', 2)),
        'per_device_eval_batch_size': int(req.get('per_device_eval_batch_size', 2)),
        'gradient_accumulation_steps': int(req.get('gradient_accumulation_steps', 1)),
        'warmup_steps': int(req.get('warmup_steps', 0)),
        'weight_decay': float(req.get('weight_decay', 0.0)),
        'max_steps': int(req.get('max_steps', -1)),
        'save_steps': int(req.get('save_steps', 1000)),
        'logging_steps': int(req.get('logging_steps', 50)),
        'eval_steps': int(req.get('eval_steps', 200)),
        'evaluation_strategy': req.get('evaluation_strategy', 'no'),
        'lora': bool(req.get('lora', True)),
        'lora_r': int(req.get('lora_r', 8)),
        'lora_alpha': int(req.get('lora_alpha', 16)),
        'lora_dropout': float(req.get('lora_dropout', 0.05)),
        'seed': int(req.get('seed', 42)),
        'fp16': bool(req.get('fp16', True)),
        'bf16': bool(req.get('bf16', False)),
        'use_8bit_adam': bool(req.get('use_8bit_adam', False)),
        'block_size': int(req.get('block_size', 1024)),
        'push_to_hub': bool(req.get('push_to_hub', False)),
        'hub_model_id': req.get('hub_model_id'),
        'hub_private_repo': bool(req.get('hub_private_repo', False))
    }

    job_id = jobs.create_job(train_config)
    runner.run_async(job_id)
    return jsonify({"job_id": job_id, "status": jobs.get_job(job_id)['status']}), 202


@app.route('/jobs', methods=['GET'])
def list_jobs():
    return jsonify(jobs.list_jobs())


@app.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route('/jobs/<job_id>/logs', methods=['GET'])
def get_job_logs(job_id):
    log_text = runner.get_job_logs(job_id)
    if log_text is None:
        return jsonify({"error": "Job not found"}), 404
    return app.response_class(log_text, mimetype='text/plain')


@app.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    ok = jobs.cancel_job(job_id)
    if not ok:
        return jsonify({"error": "Job not found or cannot cancel"}), 404
    return jsonify({"job_id": job_id, "status": jobs.get_job(job_id)['status']})


if __name__ == '__main__':
    os.makedirs(SETTINGS['DATASETS_DIR'], exist_ok=True)
    os.makedirs(SETTINGS['OUTPUTS_DIR'], exist_ok=True)
    os.makedirs(SETTINGS['LOGS_DIR'], exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))



def create_app():
    return app


@app.route('/finetune', methods=['POST'])
def _auto_stub_finetune():
    return 'Auto-generated stub for /finetune', 200
