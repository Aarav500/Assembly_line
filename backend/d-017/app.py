import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import threading
import time

app = Flask(__name__)

runners = []
runner_id_counter = 1
lock = threading.Lock()

class Runner:
    def __init__(self, runner_id, status='idle'):
        self.id = runner_id
        self.status = status
        self.last_active = time.time()

    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'last_active': self.last_active
        }

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/runners', methods=['GET'])
def get_runners():
    with lock:
        return jsonify({'runners': [r.to_dict() for r in runners]}), 200

@app.route('/runners', methods=['POST'])
def create_runner():
    global runner_id_counter
    with lock:
        runner = Runner(runner_id_counter)
        runners.append(runner)
        runner_id_counter += 1
        return jsonify(runner.to_dict()), 201

@app.route('/runners/<int:runner_id>', methods=['DELETE'])
def delete_runner(runner_id):
    with lock:
        for i, runner in enumerate(runners):
            if runner.id == runner_id:
                del runners[i]
                return jsonify({'message': 'Runner deleted'}), 200
        return jsonify({'error': 'Runner not found'}), 404

@app.route('/runners/<int:runner_id>/status', methods=['PUT'])
def update_runner_status(runner_id):
    data = request.get_json()
    status = data.get('status')
    
    if not status:
        return jsonify({'error': 'Status required'}), 400
    
    with lock:
        for runner in runners:
            if runner.id == runner_id:
                runner.status = status
                runner.last_active = time.time()
                return jsonify(runner.to_dict()), 200
        return jsonify({'error': 'Runner not found'}), 404

@app.route('/scale', methods=['POST'])
def scale_runners():
    data = request.get_json()
    desired_count = data.get('desired_count', 0)
    
    with lock:
        current_count = len(runners)
        
        if desired_count > current_count:
            global runner_id_counter
            for _ in range(desired_count - current_count):
                runner = Runner(runner_id_counter)
                runners.append(runner)
                runner_id_counter += 1
        elif desired_count < current_count:
            runners[:] = runners[:desired_count]
        
        return jsonify({
            'current_count': len(runners),
            'desired_count': desired_count
        }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app
