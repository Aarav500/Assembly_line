import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_file
import json
import os
from datetime import datetime
import zipfile
import io

app = Flask(__name__)

EVIDENCE_DIR = 'evidence'
BUNDLES_DIR = 'bundles'

if not os.path.exists(EVIDENCE_DIR):
    os.makedirs(EVIDENCE_DIR)
if not os.path.exists(BUNDLES_DIR):
    os.makedirs(BUNDLES_DIR)

evidence_store = {}

@app.route('/')
def index():
    return jsonify({'message': 'Audit Evidence Bundling API'})

@app.route('/evidence', methods=['POST'])
def add_evidence():
    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({'error': 'Missing title or content'}), 400
    
    evidence_id = str(len(evidence_store) + 1)
    evidence = {
        'id': evidence_id,
        'title': data['title'],
        'content': data['content'],
        'category': data.get('category', 'general'),
        'timestamp': datetime.now().isoformat()
    }
    evidence_store[evidence_id] = evidence
    
    filename = os.path.join(EVIDENCE_DIR, f'evidence_{evidence_id}.json')
    with open(filename, 'w') as f:
        json.dump(evidence, f, indent=2)
    
    return jsonify(evidence), 201

@app.route('/evidence', methods=['GET'])
def list_evidence():
    return jsonify(list(evidence_store.values()))

@app.route('/evidence/<evidence_id>', methods=['GET'])
def get_evidence(evidence_id):
    if evidence_id not in evidence_store:
        return jsonify({'error': 'Evidence not found'}), 404
    return jsonify(evidence_store[evidence_id])

@app.route('/bundle', methods=['POST'])
def create_bundle():
    data = request.get_json()
    evidence_ids = data.get('evidence_ids', [])
    bundle_name = data.get('name', f'audit_bundle_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    
    if not evidence_ids:
        evidence_ids = list(evidence_store.keys())
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        manifest = {'bundle_name': bundle_name, 'created_at': datetime.now().isoformat(), 'evidence': []}
        
        for eid in evidence_ids:
            if eid in evidence_store:
                evidence = evidence_store[eid]
                manifest['evidence'].append(evidence)
                filename = f'evidence_{eid}.json'
                zf.writestr(filename, json.dumps(evidence, indent=2))
        
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))
    
    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f'{bundle_name}.zip')

@app.route('/bundle/export', methods=['GET'])
def export_all():
    bundle_name = f'full_audit_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        manifest = {'bundle_name': bundle_name, 'created_at': datetime.now().isoformat(), 'evidence': []}
        
        for eid, evidence in evidence_store.items():
            manifest['evidence'].append(evidence)
            filename = f'evidence_{eid}.json'
            zf.writestr(filename, json.dumps(evidence, indent=2))
        
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))
    
    memory_file.seek(0)
    return send_file(memory_file, mimetype='application/zip', as_attachment=True, download_name=f'{bundle_name}.zip')

if __name__ == '__main__':
    app.run(debug=True, port=5000)


def create_app():
    return app
