import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime
import json
import os

app = Flask(__name__)

SNAPSHOTS_FILE = 'snapshots.json'
RUNBOOKS_FILE = 'runbooks.json'
DRILLS_FILE = 'drills.json'

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    return jsonify({
        'service': 'Disaster Recovery Management System',
        'endpoints': ['/snapshots', '/runbooks', '/drills']
    })

@app.route('/snapshots', methods=['GET', 'POST'])
def snapshots():
    if request.method == 'POST':
        data = load_data(SNAPSHOTS_FILE)
        snapshot = {
            'id': len(data) + 1,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'completed',
            'size_mb': request.json.get('size_mb', 0)
        }
        data.append(snapshot)
        save_data(SNAPSHOTS_FILE, data)
        return jsonify(snapshot), 201
    
    return jsonify(load_data(SNAPSHOTS_FILE))

@app.route('/runbooks', methods=['GET', 'POST'])
def runbooks():
    if request.method == 'POST':
        data = load_data(RUNBOOKS_FILE)
        runbook = {
            'id': len(data) + 1,
            'name': request.json.get('name', 'Untitled Runbook'),
            'steps': request.json.get('steps', []),
            'created_at': datetime.utcnow().isoformat()
        }
        data.append(runbook)
        save_data(RUNBOOKS_FILE, data)
        return jsonify(runbook), 201
    
    return jsonify(load_data(RUNBOOKS_FILE))

@app.route('/drills', methods=['GET', 'POST'])
def drills():
    if request.method == 'POST':
        data = load_data(DRILLS_FILE)
        drill = {
            'id': len(data) + 1,
            'runbook_id': request.json.get('runbook_id'),
            'status': 'in_progress',
            'started_at': datetime.utcnow().isoformat(),
            'results': {}
        }
        data.append(drill)
        save_data(DRILLS_FILE, data)
        return jsonify(drill), 201
    
    return jsonify(load_data(DRILLS_FILE))

@app.route('/drills/<int:drill_id>/complete', methods=['POST'])
def complete_drill(drill_id):
    data = load_data(DRILLS_FILE)
    for drill in data:
        if drill['id'] == drill_id:
            drill['status'] = 'completed'
            drill['completed_at'] = datetime.utcnow().isoformat()
            drill['results'] = request.json.get('results', {})
            save_data(DRILLS_FILE, data)
            return jsonify(drill)
    return jsonify({'error': 'Drill not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app
