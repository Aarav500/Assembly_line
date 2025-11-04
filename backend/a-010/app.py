import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import json
import shutil
import tempfile
import time
from zipfile import ZipFile
from pathlib import Path
from flask import Flask, request, jsonify, render_template, redirect, url_for
from werkzeug.utils import secure_filename

from config import get_config
from feature_extractor import extract_features
from ideater_client import IdeaterClient

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
config = get_config()
app.config['SECRET_KEY'] = config['SECRET_KEY']
app.config['TESTING'] = os.getenv('TESTING', 'false').lower() == 'true'

# Simple in-memory store for import results (fallback)
IMPORT_RESULTS = {}


def _extract_upload_to_dir(file_storage):
    tmpdir = Path(tempfile.mkdtemp(prefix='ideater_import_'))
    try:
        filename = secure_filename(file_storage.filename or 'project.zip')
        if not filename:
            filename = 'project.zip'
        upload_path = tmpdir / filename
        file_storage.save(str(upload_path))
        project_dir = tmpdir / 'project'
        project_dir.mkdir(parents=True, exist_ok=True)

        # If it's a zip, extract; otherwise try to just move it
        if str(upload_path).lower().endswith('.zip'):
            with ZipFile(upload_path, 'r') as zf:
                zf.extractall(project_dir)
        else:
            # Assume it's a single file project, copy into dir
            shutil.copy(upload_path, project_dir / filename)

        return tmpdir, project_dir
    except Exception as e:
        # Clean up on error
        if tmpdir.exists():
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _download_zip_to_dir(url: str):
    import requests
    tmpdir = Path(tempfile.mkdtemp(prefix='ideater_import_'))
    try:
        project_dir = tmpdir / 'project'
        project_dir.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        zip_path = tmpdir / 'project.zip'
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        with ZipFile(zip_path, 'r') as zf:
            zf.extractall(project_dir)
        return tmpdir, project_dir
    except Exception as e:
        # Clean up on error
        if tmpdir.exists():
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', workspace_url=config.get('IDEATER_WORKSPACE_URL', ''))


@app.route('/api/ideater/import', methods=['POST'])
def api_ideater_import():
    # Inputs can be: multipart with file 'project', and optional metadata; or JSON with project_zip_url
    cleanup_dirs = []
    try:
        source = {
            'name': request.form.get('source_name') or (request.json.get('source_name') if request.is_json else None) or 'Imported Project',
            'url': request.form.get('source_url') or (request.json.get('source_url') if request.is_json else None),
        }
        workspace_id = request.form.get('workspace_id') or (request.json.get('workspace_id') if request.is_json else None) or config.get('IDEATER_WORKSPACE_ID')
        if not workspace_id:
            workspace_id = config.get('IDEATER_WORKSPACE_ID')

        # Obtain project directory
        project_dir = None
        if 'project' in request.files:
            tmpdir, project_dir = _extract_upload_to_dir(request.files['project'])
            cleanup_dirs.append(tmpdir)
        elif request.is_json and request.json.get('project_zip_url'):
            tmpdir, project_dir = _download_zip_to_dir(request.json['project_zip_url'])
            cleanup_dirs.append(tmpdir)
        elif request.form.get('project_zip_url'):
            tmpdir, project_dir = _download_zip_to_dir(request.form.get('project_zip_url'))
            cleanup_dirs.append(tmpdir)
        else:
            return jsonify({'error': 'No project upload or project_zip_url provided'}), 400

        # Feature extraction
        features = extract_features(project_dir)
        if not features:
            return jsonify({'error': 'No features discovered in project'}), 422

        # Send to Ideater
        client = IdeaterClient(
            base_url=config.get('IDEATER_API_BASE'),
            import_endpoint=config.get('IDEATER_IMPORT_ENDPOINT'),
            token=config.get('IDEATER_API_TOKEN'),
            workspace_id=workspace_id,
            workspace_url=config.get('IDEATER_WORKSPACE_URL'),
        )
        import_result = client.import_features(features, source)

        # Store result for viewing
        import_id = import_result.get('import_id') or str(uuid.uuid4())
        IMPORT_RESULTS[import_id] = import_result

        # Respond with JSON if requested via fetch, else redirect to result page
        if request.headers.get('Accept', '').lower().startswith('application/json') or request.is_json:
            return jsonify({'ok': True, 'import_id': import_id, 'summary': import_result.get('summary'), 'open_url': import_result.get('open_url')})
        else:
            return redirect(url_for('import_result', import_id=import_id))

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp dirs
        for d in cleanup_dirs:
            try:
                if d and Path(d).exists():
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass


@app.route('/import/result/<import_id>', methods=['GET'])
def import_result(import_id):
    data = IMPORT_RESULTS.get(import_id)
    if not data:
        return render_template('result.html', error='Import not found', import_id=import_id)
    return render_template('result.html', result=data, import_id=import_id)


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}


def create_app():
    return app


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)