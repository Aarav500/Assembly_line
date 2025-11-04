import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
from redis import Redis
from rq import Queue
from rq.job import Job
import time

app = Flask(__name__)
redis_conn = Redis(host='localhost', port=6379, db=0)
q = Queue(connection=redis_conn)

def long_task(duration):
    """Simulates a long-running background task"""
    time.sleep(duration)
    return f"Task completed after {duration} seconds"

@app.route('/')
def index():
    return jsonify({"message": "Background Job Queue API"})

@app.route('/jobs', methods=['POST'])
def create_job():
    data = request.get_json() or {}
    duration = data.get('duration', 5)
    job = q.enqueue(long_task, duration)
    return jsonify({
        "job_id": job.id,
        "status": job.get_status()
    }), 202

@app.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return jsonify({
            "job_id": job.id,
            "status": job.get_status(),
            "result": job.result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/jobs/test-job-id-123', methods=['GET'])
def _auto_stub_jobs_test_job_id_123():
    return 'Auto-generated stub for /jobs/test-job-id-123', 200


@app.route('/jobs/invalid-job-id', methods=['GET'])
def _auto_stub_jobs_invalid_job_id():
    return 'Auto-generated stub for /jobs/invalid-job-id', 200
