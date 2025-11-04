import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

BACKUPS_FILE = 'backups.json'
RETENTION_DAYS = 7

def load_backups():
    if os.path.exists(BACKUPS_FILE):
        with open(BACKUPS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_backups(backups):
    with open(BACKUPS_FILE, 'w') as f:
        json.dump(backups, f, indent=2)

def apply_retention_policy(backups):
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    return [b for b in backups if datetime.fromisoformat(b['timestamp']) > cutoff_date]

@app.route('/')
def index():
    return jsonify({'message': 'Backup & Restore Automation API'})

@app.route('/backup', methods=['POST'])
def create_backup():
    data = request.json
    if not data or 'name' not in data:
        return jsonify({'error': 'Backup name required'}), 400
    
    backups = load_backups()
    backup = {
        'id': len(backups) + 1,
        'name': data['name'],
        'data': data.get('data', {}),
        'timestamp': datetime.now().isoformat()
    }
    backups.append(backup)
    backups = apply_retention_policy(backups)
    save_backups(backups)
    
    return jsonify({'message': 'Backup created', 'backup': backup}), 201

@app.route('/backups', methods=['GET'])
def list_backups():
    backups = load_backups()
    backups = apply_retention_policy(backups)
    save_backups(backups)
    return jsonify({'backups': backups})

@app.route('/restore/<int:backup_id>', methods=['POST'])
def restore_backup(backup_id):
    backups = load_backups()
    backup = next((b for b in backups if b['id'] == backup_id), None)
    
    if not backup:
        return jsonify({'error': 'Backup not found'}), 404
    
    return jsonify({'message': 'Backup restored', 'backup': backup})

@app.route('/drill', methods=['POST'])
def restore_drill():
    data = request.json
    if not data or 'backup_id' not in data:
        return jsonify({'error': 'Backup ID required for drill'}), 400
    
    backups = load_backups()
    backup = next((b for b in backups if b['id'] == data['backup_id']), None)
    
    if not backup:
        return jsonify({'error': 'Backup not found'}), 404
    
    drill_result = {
        'drill_id': f"drill_{datetime.now().timestamp()}",
        'backup_id': backup['id'],
        'status': 'success',
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify({'message': 'Restore drill completed', 'result': drill_result})

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app
