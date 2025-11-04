import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json

app = Flask(__name__)

schedules = {}
handoffs = []


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/schedules', methods=['GET', 'POST'])
def manage_schedules():
    if request.method == 'POST':
        data = request.get_json()
        schedule_id = data.get('id')
        schedules[schedule_id] = {
            'id': schedule_id,
            'engineer': data.get('engineer'),
            'start_time': data.get('start_time'),
            'end_time': data.get('end_time')
        }
        return jsonify(schedules[schedule_id]), 201
    return jsonify(list(schedules.values())), 200


@app.route('/schedules/<schedule_id>', methods=['GET'])
def get_schedule(schedule_id):
    if schedule_id in schedules:
        return jsonify(schedules[schedule_id]), 200
    return jsonify({'error': 'Schedule not found'}), 404


@app.route('/handoff', methods=['POST'])
def create_handoff():
    data = request.get_json()
    handoff = {
        'id': len(handoffs) + 1,
        'from_engineer': data.get('from_engineer'),
        'to_engineer': data.get('to_engineer'),
        'notes': data.get('notes', ''),
        'timestamp': datetime.utcnow().isoformat()
    }
    handoffs.append(handoff)
    return jsonify(handoff), 201


@app.route('/handoffs', methods=['GET'])
def get_handoffs():
    return jsonify(handoffs), 200


@app.route('/current-oncall', methods=['GET'])
def get_current_oncall():
    now = datetime.utcnow().isoformat()
    for schedule in schedules.values():
        if schedule['start_time'] <= now <= schedule['end_time']:
            return jsonify(schedule), 200
    return jsonify({'error': 'No engineer on-call'}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5000)



def create_app():
    return app
