import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from datetime import datetime
import os

app = Flask(__name__)

ROLLOUT_STAGES = {
    'canary': {'percentage': 5, 'start_hour': 0},
    'stage1': {'percentage': 25, 'start_hour': 2},
    'stage2': {'percentage': 50, 'start_hour': 4},
    'stage3': {'percentage': 100, 'start_hour': 6}
}

RELEASE_START_TIME = os.getenv('RELEASE_START_TIME', '2024-01-01T00:00:00')

def get_current_stage():
    release_start = datetime.fromisoformat(RELEASE_START_TIME)
    now = datetime.utcnow()
    hours_elapsed = (now - release_start).total_seconds() / 3600
    
    current_stage = 'canary'
    for stage, config in ROLLOUT_STAGES.items():
        if hours_elapsed >= config['start_hour']:
            current_stage = stage
    
    return current_stage, ROLLOUT_STAGES[current_stage]

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'service': 'staged-rollout'})

@app.route('/rollout/status')
def rollout_status():
    stage, config = get_current_stage()
    return jsonify({
        'current_stage': stage,
        'percentage': config['percentage'],
        'release_start': RELEASE_START_TIME
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


def create_app():
    return app
