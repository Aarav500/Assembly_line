import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from datetime import datetime
import json

app = Flask(__name__)

flaky_tests = {}
test_results = []
owners = {}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/test-result', methods=['POST'])
def record_test_result():
    data = request.json
    test_name = data.get('test_name')
    status = data.get('status')

    if not test_name or not status:
        return jsonify({'error': 'test_name and status required'}), 400

    result = {
        'test_name': test_name,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }
    test_results.append(result)

    if test_name not in flaky_tests:
        flaky_tests[test_name] = {'passes': 0, 'failures': 0, 'retests_scheduled': 0}

    if status == 'pass':
        flaky_tests[test_name]['passes'] += 1
    else:
        flaky_tests[test_name]['failures'] += 1

    total = flaky_tests[test_name]['passes'] + flaky_tests[test_name]['failures']
    failure_rate = flaky_tests[test_name]['failures'] / total if total > 0 else 0

    is_flaky = False
    if total >= 3 and 0.2 <= failure_rate <= 0.8:
        is_flaky = True
        flaky_tests[test_name]['retests_scheduled'] += 1

    return jsonify({
        'recorded': True,
        'is_flaky': is_flaky,
        'retest_scheduled': is_flaky
    }), 201

@app.route('/flaky-tests', methods=['GET'])
def get_flaky_tests():
    flaky_list = []
    for test_name, stats in flaky_tests.items():
        total = stats['passes'] + stats['failures']
        if total >= 3:
            failure_rate = stats['failures'] / total
            if 0.2 <= failure_rate <= 0.8:
                owner = owners.get(test_name, 'unassigned')
                flaky_list.append({
                    'test_name': test_name,
                    'failure_rate': round(failure_rate, 2),
                    'retests_scheduled': stats['retests_scheduled'],
                    'owner': owner
                })
    return jsonify({'flaky_tests': flaky_list}), 200

@app.route('/assign-owner', methods=['POST'])
def assign_owner():
    data = request.json
    test_name = data.get('test_name')
    owner = data.get('owner')

    if not test_name or not owner:
        return jsonify({'error': 'test_name and owner required'}), 400

    owners[test_name] = owner
    return jsonify({'assigned': True, 'test_name': test_name, 'owner': owner}), 200

@app.route('/schedule-retest', methods=['POST'])
def schedule_retest():
    data = request.json
    test_name = data.get('test_name')

    if not test_name:
        return jsonify({'error': 'test_name required'}), 400

    if test_name in flaky_tests:
        flaky_tests[test_name]['retests_scheduled'] += 1

    return jsonify({
        'scheduled': True,
        'test_name': test_name,
        'total_retests': flaky_tests.get(test_name, {}).get('retests_scheduled', 1)
    }), 200

if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app
