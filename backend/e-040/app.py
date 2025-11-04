import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime
import uuid

app = Flask(__name__)

scans = {}
remediation_tasks = {}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})

@app.route('/scans', methods=['GET', 'POST'])
def handle_scans():
    if request.method == 'POST':
        data = request.get_json()
        scan_id = str(uuid.uuid4())
        scan = {
            'id': scan_id,
            'target': data.get('target'),
            'timestamp': datetime.utcnow().isoformat(),
            'findings': data.get('findings', []),
            'compliance_score': data.get('compliance_score', 0)
        }
        scans[scan_id] = scan
        return jsonify(scan), 201
    return jsonify(list(scans.values()))

@app.route('/scans/<scan_id>', methods=['GET'])
def get_scan(scan_id):
    scan = scans.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify(scan)

@app.route('/scans/<scan_id>/report', methods=['GET'])
def get_scan_report(scan_id):
    scan = scans.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    
    report = {
        'scan_id': scan_id,
        'target': scan['target'],
        'timestamp': scan['timestamp'],
        'compliance_score': scan['compliance_score'],
        'total_findings': len(scan['findings']),
        'critical_findings': len([f for f in scan['findings'] if f.get('severity') == 'critical']),
        'high_findings': len([f for f in scan['findings'] if f.get('severity') == 'high']),
        'findings': scan['findings']
    }
    return jsonify(report)

@app.route('/remediation', methods=['GET', 'POST'])
def handle_remediation():
    if request.method == 'POST':
        data = request.get_json()
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'scan_id': data.get('scan_id'),
            'finding_id': data.get('finding_id'),
            'action': data.get('action'),
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }
        remediation_tasks[task_id] = task
        return jsonify(task), 201
    return jsonify(list(remediation_tasks.values()))

@app.route('/remediation/<task_id>', methods=['GET', 'PATCH'])
def handle_remediation_task(task_id):
    task = remediation_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if request.method == 'PATCH':
        data = request.get_json()
        task['status'] = data.get('status', task['status'])
        task['updated_at'] = datetime.utcnow().isoformat()
        return jsonify(task)
    
    return jsonify(task)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


def create_app():
    return app
