import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import json
import shutil
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_file, render_template

from src.extractor.zip_utils import extract_zip_to, make_zip_from_dir
from src.extractor.analyzer import analyze_directory
from src.extractor.replacer import refactor_directory_with_components

app = Flask(__name__)
app.config.from_object('config.Config')

executor = ThreadPoolExecutor(max_workers=2)
jobs = {}


def job_dir(job_id):
    base = app.config['JOBS_DIR']
    path = os.path.join(base, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def run_analysis_job(job_id, zip_path):
    jobs[job_id]['status'] = 'running'
    jobs[job_id]['message'] = 'Unpacking input bundle'
    try:
        base_dir = job_dir(job_id)
        input_dir = os.path.join(base_dir, 'input')
        work_dir = os.path.join(base_dir, 'work')
        output_dir = os.path.join(base_dir, 'output')
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        extract_zip_to(zip_path, input_dir)
        jobs[job_id]['message'] = 'Analyzing components'

        # Analyze input directory to identify reusable components
        analysis = analyze_directory(input_dir,
                                     min_occurrences=app.config['MIN_OCCURRENCES'],
                                     min_length=app.config['MIN_SNIPPET_LENGTH'],
                                     max_components=app.config['MAX_COMPONENTS'])

        jobs[job_id]['message'] = f"Found {len(analysis['components'])} candidate components. Refactoring..."

        # Refactor files using identified components
        refactor_result = refactor_directory_with_components(
            input_dir=input_dir,
            output_dir=output_dir,
            components=analysis['components']
        )

        # Write metadata
        metadata = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'components': analysis['components'],
            'stats': refactor_result['stats']
        }
        meta_path = os.path.join(output_dir, 'component_library.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Package result
        result_zip = os.path.join(base_dir, 'result.zip')
        make_zip_from_dir(output_dir, result_zip)

        jobs[job_id]['status'] = 'done'
        jobs[job_id]['result'] = result_zip
        jobs[job_id]['message'] = 'Completed'

    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = str(e)
        jobs[job_id]['trace'] = traceback.format_exc()

    finally:
        # cleanup uploaded zip
        try:
            os.remove(zip_path)
        except Exception:
            pass


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/job/<job_id>')
def job_page(job_id):
    if job_id not in jobs:
        return render_template('job.html', job_id=job_id, status='unknown', message='Job not found'), 404
    return render_template('job.html', job_id=job_id, status=jobs[job_id]['status'], message=jobs[job_id].get('message', ''))


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    job_id = uuid.uuid4().hex
    base = job_dir(job_id)
    upload_path = os.path.join(base, 'upload.zip')
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    f.save(upload_path)

    jobs[job_id] = {
        'id': job_id,
        'status': 'queued',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'message': 'Queued'
    }

    executor.submit(run_analysis_job, job_id, upload_path)

    return jsonify({'job_id': job_id, 'status_url': f"/api/jobs/{job_id}", 'download_url': f"/api/jobs/{job_id}/download"})


@app.route('/api/jobs/<job_id>')
def api_job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Not found'}), 404
    resp = {
        'id': job_id,
        'status': job['status'],
        'message': job.get('message', ''),
    }
    if job['status'] == 'done':
        resp['download_url'] = f"/api/jobs/{job_id}/download"
    if job['status'] == 'error':
        resp['trace'] = job.get('trace', '')
    return jsonify(resp)


@app.route('/api/jobs/<job_id>/download')
def api_job_download(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Not found'}), 404
    if job['status'] != 'done' or 'result' not in job:
        return jsonify({'error': 'Not ready'}), 400
    return send_file(job['result'], as_attachment=True, download_name=f"refactored_{job_id}.zip")


if __name__ == '__main__':
    os.makedirs(app.config['JOBS_DIR'], exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/extract', methods=['POST'])
def _auto_stub_extract():
    return 'Auto-generated stub for /extract', 200


@app.route('/components', methods=['GET'])
def _auto_stub_components():
    return 'Auto-generated stub for /components', 200
