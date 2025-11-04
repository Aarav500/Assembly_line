import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
import os
import subprocess
import tempfile
import shutil

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_pr():
    data = request.get_json()
    files = data.get('files', [])
    
    temp_dir = tempfile.mkdtemp()
    try:
        for file_data in files:
            file_path = os.path.join(temp_dir, file_data['path'])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(file_data['content'])
        
        result = {
            'status': 'success',
            'files': [f['path'] for f in files],
            'preview_path': temp_dir
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/api/diff', methods=['POST'])
def get_diff():
    data = request.get_json()
    original = data.get('original', '')
    modified = data.get('modified', '')
    
    import difflib
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile='original',
        tofile='modified'
    ))
    
    return jsonify({'diff': ''.join(diff)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
