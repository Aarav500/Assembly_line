import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
import datetime
import threading
import time

app = Flask(__name__)

cve_scan_results = []
last_scan_time = None
results_lock = threading.Lock()


def mock_cve_scan():
    """Simulate a CVE scan of production images"""
    images = ['nginx:latest', 'postgres:14', 'redis:7']
    results = []
    for image in images:
        vulnerabilities = {
            'critical': 0,
            'high': 1,
            'medium': 2,
            'low': 3
        }
        results.append({
            'image': image,
            'vulnerabilities': vulnerabilities,
            'scan_time': datetime.datetime.utcnow().isoformat()
        })
    return results


def scheduled_scan_job():
    """Background job that runs CVE scans periodically"""
    global cve_scan_results, last_scan_time
    while True:
        with results_lock:
            cve_scan_results = mock_cve_scan()
            last_scan_time = datetime.datetime.utcnow()
        time.sleep(3600)  # Run every hour


@app.route('/')
def home():
    with results_lock:
        scan_time = last_scan_time.isoformat() if last_scan_time else 'No scans yet'
    return jsonify({
        'service': 'CVE Re-check Service',
        'status': 'running',
        'last_scan': scan_time
    })


@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200


@app.route('/scan/results')
def get_scan_results():
    with results_lock:
        if not cve_scan_results:
            return jsonify({'message': 'No scan results available yet'}), 404
        return jsonify({
            'last_scan': last_scan_time.isoformat() if last_scan_time else None,
            'results': cve_scan_results
        })


@app.route('/scan/trigger', methods=['POST'])
def trigger_scan():
    global cve_scan_results, last_scan_time
    with results_lock:
        cve_scan_results = mock_cve_scan()
        last_scan_time = datetime.datetime.utcnow()
        scan_time = last_scan_time.isoformat()
    return jsonify({
        'message': 'Scan triggered successfully',
        'scan_time': scan_time
    }), 201


if __name__ == '__main__':
    # Start background scan job
    scan_thread = threading.Thread(target=scheduled_scan_job, daemon=True)
    scan_thread.start()

    app.run(host='0.0.0.0', port=5000, debug=False)


def create_app():
    return app
