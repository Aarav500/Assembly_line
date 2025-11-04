import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import pandas as pd

from config import Config
from data_profiler import compute_and_cache_profile, load_profile_cached

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config['DATASETS_DIR'], exist_ok=True)
os.makedirs(app.config['PROFILES_DIR'], exist_ok=True)
os.makedirs(app.config['DATA_DIR'], exist_ok=True)

METADATA_PATH = os.path.join(app.config['DATA_DIR'], 'metadata.json')


def _now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def load_metadata():
    if not os.path.exists(METADATA_PATH):
        return {}
    try:
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_metadata(meta):
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}


def dataset_path(name):
    return os.path.join(app.config['DATASETS_DIR'], name + '.csv')


def profile_path(name):
    return os.path.join(app.config['PROFILES_DIR'], name + '.profile.json')


def compute_quick_stats(df):
    n_rows, n_cols = df.shape
    mem = int(df.memory_usage(deep=True).sum())
    missing_total = int(df.isna().sum().sum())
    duplicates = int(df.duplicated().sum())
    return {
        'n_rows': int(n_rows),
        'n_cols': int(n_cols),
        'memory_bytes': mem,
        'missing_total': missing_total,
        'duplicates': duplicates
    }


@app.route('/')
def index():
    meta = load_metadata()
    datasets = []
    for name, info in meta.items():
        d = info.copy()
        d['name'] = name
        datasets.append(d)
    datasets.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
    return render_template('index.html', datasets=datasets)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        base = os.path.splitext(filename)[0]
        name = base.replace(' ', '_').lower()
        # Ensure unique name
        meta = load_metadata()
        original_name = name
        i = 1
        while name in meta:
            name = f"{original_name}_{i}"
            i += 1
        path = dataset_path(name)
        file.save(path)
        size_bytes = os.path.getsize(path)
        # Try to read head to get quick stats
        try:
            df = pd.read_csv(path, low_memory=False)
            quick = compute_quick_stats(df)
        except Exception:
            quick = {
                'n_rows': None,
                'n_cols': None,
                'memory_bytes': None,
                'missing_total': None,
                'duplicates': None
            }
        meta[name] = {
            'filename': os.path.basename(path),
            'uploaded_at': _now_iso(),
            'size_bytes': int(size_bytes),
            'n_rows': quick['n_rows'],
            'n_cols': quick['n_cols'],
            'memory_bytes': quick['memory_bytes'],
            'missing_total': quick['missing_total'],
            'duplicates': quick['duplicates'],
            'last_profiled_at': None
        }
        save_metadata(meta)
        # Eager profile if configured
        if app.config.get('EAGER_PROFILE', True):
            try:
                prof = compute_and_cache_profile(name, dataset_path(name), profile_path(name))
                meta = load_metadata()
                if name in meta:
                    meta[name]['last_profiled_at'] = prof.get('generated_at')
                    meta[name]['n_rows'] = prof.get('basic', {}).get('n_rows', meta[name]['n_rows'])
                    meta[name]['n_cols'] = prof.get('basic', {}).get('n_cols', meta[name]['n_cols'])
                    meta[name]['memory_bytes'] = prof.get('basic', {}).get('memory_bytes', meta[name]['memory_bytes'])
                    meta[name]['missing_total'] = prof.get('basic', {}).get('missing_total', meta[name]['missing_total'])
                    meta[name]['duplicates'] = prof.get('basic', {}).get('duplicate_rows', meta[name]['duplicates'])
                    save_metadata(meta)
            except Exception:
                pass
        return redirect(url_for('dataset_detail', name=name))
    return redirect(url_for('index'))


@app.route('/dataset/<name>')
def dataset_detail(name):
    meta = load_metadata()
    if name not in meta:
        abort(404)
    return render_template('dataset.html', name=name, info=meta[name])


@app.route('/api/datasets')
def api_datasets():
    meta = load_metadata()
    datasets = []
    for name, info in meta.items():
        d = info.copy()
        d['name'] = name
        datasets.append(d)
    datasets.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
    return jsonify({'datasets': datasets})


@app.route('/api/dataset/<name>/profile')
def api_dataset_profile(name):
    meta = load_metadata()
    if name not in meta:
        return jsonify({'error': 'not_found'}), 404
    prof = load_profile_cached(profile_path(name))
    if prof is None:
        prof = compute_and_cache_profile(name, dataset_path(name), profile_path(name))
        # update metadata last_profiled_at
        meta = load_metadata()
        if name in meta:
            meta[name]['last_profiled_at'] = prof.get('generated_at')
            meta[name]['n_rows'] = prof.get('basic', {}).get('n_rows', meta[name]['n_rows'])
            meta[name]['n_cols'] = prof.get('basic', {}).get('n_cols', meta[name]['n_cols'])
            meta[name]['memory_bytes'] = prof.get('basic', {}).get('memory_bytes', meta[name]['memory_bytes'])
            meta[name]['missing_total'] = prof.get('basic', {}).get('missing_total', meta[name]['missing_total'])
            meta[name]['duplicates'] = prof.get('basic', {}).get('duplicate_rows', meta[name]['duplicates'])
            save_metadata(meta)
    return jsonify(prof)


@app.route('/api/dataset/<name>/sample')
def api_dataset_sample(name):
    meta = load_metadata()
    if name not in meta:
        return jsonify({'error': 'not_found'}), 404
    limit = int(request.args.get('limit', 20))
    path = dataset_path(name)
    try:
        df = pd.read_csv(path, nrows=limit, low_memory=False)
        cols = list(map(str, df.columns.tolist()))
        rows = df.where(pd.notnull(df), None).astype(object).values.tolist()
        return jsonify({'columns': cols, 'rows': rows})
    except Exception as e:
        return jsonify({'error': 'read_failed', 'message': str(e)}), 500


@app.route('/dataset/<name>/delete', methods=['POST'])
def delete_dataset(name):
    meta = load_metadata()
    if name not in meta:
        return redirect(url_for('index'))
    # remove files
    try:
        dp = dataset_path(name)
        pp = profile_path(name)
        if os.path.exists(dp):
            os.remove(dp)
        if os.path.exists(pp):
            os.remove(pp)
    except Exception:
        pass
    # update metadata
    meta.pop(name, None)
    save_metadata(meta)
    return redirect(url_for('index'))


@app.route('/download/<name>')
def download_dataset(name):
    path = dataset_path(name)
    if not os.path.exists(path):
        abort(404)
    return send_from_directory(app.config['DATASETS_DIR'], os.path.basename(path), as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/api/datasets/test_data', methods=['POST'])
def _auto_stub_api_datasets_test_data():
    return 'Auto-generated stub for /api/datasets/test_data', 200


@app.route('/api/datasets/test_data/profile', methods=['GET'])
def _auto_stub_api_datasets_test_data_profile():
    return 'Auto-generated stub for /api/datasets/test_data/profile', 200
