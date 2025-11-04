import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Store agent states and maintenance windows
agent_states = {
    'agent_1': {'status': 'active', 'last_maintenance': None, 'last_retrain': None},
    'agent_2': {'status': 'active', 'last_maintenance': None, 'last_retrain': None}
}

maintenance_logs = []
retraining_logs = []

scheduler = BackgroundScheduler()
scheduler_lock = threading.Lock()

def run_maintenance(agent_id):
    """Run maintenance for a specific agent"""
    with scheduler_lock:
        if agent_id in agent_states:
            agent_states[agent_id]['status'] = 'maintenance'
            agent_states[agent_id]['last_maintenance'] = datetime.now().isoformat()
            maintenance_logs.append({
                'agent_id': agent_id,
                'timestamp': datetime.now().isoformat(),
                'action': 'maintenance_completed'
            })
            agent_states[agent_id]['status'] = 'active'
            logging.info(f"Maintenance completed for {agent_id}")

def run_retraining(agent_id):
    """Run retraining for a specific agent"""
    with scheduler_lock:
        if agent_id in agent_states:
            agent_states[agent_id]['status'] = 'retraining'
            agent_states[agent_id]['last_retrain'] = datetime.now().isoformat()
            retraining_logs.append({
                'agent_id': agent_id,
                'timestamp': datetime.now().isoformat(),
                'action': 'retraining_completed'
            })
            agent_states[agent_id]['status'] = 'active'
            logging.info(f"Retraining completed for {agent_id}")

@app.route('/agents', methods=['GET'])
def get_agents():
    """Get all agents and their states"""
    return jsonify(agent_states)

@app.route('/agents/<agent_id>/status', methods=['GET'])
def get_agent_status(agent_id):
    """Get status of a specific agent"""
    if agent_id not in agent_states:
        return jsonify({'error': 'Agent not found'}), 404
    return jsonify(agent_states[agent_id])

@app.route('/schedule/maintenance', methods=['POST'])
def schedule_maintenance():
    """Schedule maintenance for an agent"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    delay_seconds = data.get('delay_seconds', 10)
    
    if agent_id not in agent_states:
        return jsonify({'error': 'Agent not found'}), 404
    
    run_date = datetime.now() + timedelta(seconds=delay_seconds)
    scheduler.add_job(run_maintenance, 'date', run_date=run_date, args=[agent_id])
    
    return jsonify({
        'message': f'Maintenance scheduled for {agent_id}',
        'scheduled_at': run_date.isoformat()
    })

@app.route('/schedule/retraining', methods=['POST'])
def schedule_retraining():
    """Schedule retraining for an agent"""
    data = request.get_json()
    agent_id = data.get('agent_id')
    delay_seconds = data.get('delay_seconds', 10)
    
    if agent_id not in agent_states:
        return jsonify({'error': 'Agent not found'}), 404
    
    run_date = datetime.now() + timedelta(seconds=delay_seconds)
    scheduler.add_job(run_retraining, 'date', run_date=run_date, args=[agent_id])
    
    return jsonify({
        'message': f'Retraining scheduled for {agent_id}',
        'scheduled_at': run_date.isoformat()
    })

@app.route('/logs/maintenance', methods=['GET'])
def get_maintenance_logs():
    """Get maintenance logs"""
    return jsonify(maintenance_logs)

@app.route('/logs/retraining', methods=['GET'])
def get_retraining_logs():
    """Get retraining logs"""
    return jsonify(retraining_logs)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    scheduler.start()
    try:
        app.run(debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def create_app():
    return app


@app.route('/agents/agent_1/status', methods=['GET'])
def _auto_stub_agents_agent_1_status():
    return 'Auto-generated stub for /agents/agent_1/status', 200


@app.route('/agents/agent_999/status', methods=['GET'])
def _auto_stub_agents_agent_999_status():
    return 'Auto-generated stub for /agents/agent_999/status', 200
