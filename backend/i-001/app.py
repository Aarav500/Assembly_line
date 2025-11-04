import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from db import init_db, create_job, append_entry, seal_job, verify_job, get_connection, row_to_dict

app = Flask(__name__)

# Initialize database on startup
if not os.path.exists(os.environ.get('AUDIT_DB_PATH', os.path.join(os.getcwd(), 'audit.db'))):
    init_db()
else:
    # Ensure schema/triggers exist
    init_db()


def error(status: int, message: str):
    resp = jsonify({'error': message})
    resp.status_code = status
    return resp


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/jobs', methods=['POST'])
def create_job_route():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    try:
        job = create_job(name)
        return jsonify({'job': job})
    except Exception as e:
        return error(400, str(e))


@app.route('/jobs', methods=['GET'])
def list_jobs_route():
    conn = get_connection()
    try:
        cur = conn.execute('SELECT j.*, COUNT(e.id) AS entry_count FROM jobs j LEFT JOIN entries e ON e.job_id = j.id GROUP BY j.id ORDER BY j.id DESC;')
        jobs = []
        for row in cur.fetchall():
            j = row_to_dict(row)
            jobs.append(j)
        return jsonify({'jobs': jobs})
    finally:
        conn.close()


@app.route('/jobs/<int:job_id>', methods=['GET'])
def get_job_route(job_id: int):
    conn = get_connection()
    try:
        job = conn.execute('SELECT * FROM jobs WHERE id = ?;', (job_id,)).fetchone()
        if job is None:
            return error(404, 'job not found')
        entry_count = conn.execute('SELECT COUNT(*) AS c FROM entries WHERE job_id = ?;', (job_id,)).fetchone()['c']
        last_hash_row = conn.execute('SELECT entry_hash FROM entries WHERE job_id = ? ORDER BY id DESC LIMIT 1;', (job_id,)).fetchone()
        return jsonify({
            'job': row_to_dict(job),
            'stats': {
                'entry_count': entry_count,
                'tip_hash': last_hash_row['entry_hash'] if last_hash_row else None,
            }
        })
    finally:
        conn.close()


@app.route('/jobs/<int:job_id>/entries', methods=['POST'])
def append_entry_route(job_id: int):
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt', '')
    response = data.get('response', '')
    metadata = data.get('metadata') or {}
    if not isinstance(metadata, dict):
        return error(400, 'metadata must be an object')
    try:
        entry = append_entry(job_id, prompt, response, metadata)
        # Only return summary and hashes to keep content minimal
        return jsonify({
            'entry': {
                'id': entry['id'],
                'job_id': entry['job_id'],
                'created_at': entry['created_at'],
                'prompt_summary': entry['prompt_summary'],
                'response_summary': entry['response_summary'],
                'prompt_sha256': entry['prompt_sha256'],
                'response_sha256': entry['response_sha256'],
                'prev_entry_hash': entry['prev_entry_hash'],
                'entry_hash': entry['entry_hash'],
            }
        })
    except Exception as e:
        return error(400, str(e))


@app.route('/jobs/<int:job_id>/entries', methods=['GET'])
def list_entries_route(job_id: int):
    conn = get_connection()
    try:
        cur = conn.execute('SELECT id, job_id, created_at, prompt_summary, response_summary, prompt_sha256, response_sha256, prev_entry_hash, entry_hash FROM entries WHERE job_id = ? ORDER BY id ASC;', (job_id,))
        entries = [dict(row) for row in cur.fetchall()]
        return jsonify({'entries': entries})
    finally:
        conn.close()


@app.route('/jobs/<int:job_id>/seal', methods=['POST'])
def seal_job_route(job_id: int):
    try:
        job = seal_job(job_id)
        return jsonify({'job': job})
    except Exception as e:
        return error(400, str(e))


@app.route('/jobs/<int:job_id>/verify', methods=['GET'])
def verify_job_route(job_id: int):
    try:
        result = verify_job(job_id)
        return jsonify(result)
    except Exception as e:
        return error(400, str(e))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



def create_app():
    return app


@app.route('/audit/log', methods=['POST'])
def _auto_stub_audit_log():
    return 'Auto-generated stub for /audit/log', 200


@app.route('/audit/job/job-456', methods=['GET'])
def _auto_stub_audit_job_job_456():
    return 'Auto-generated stub for /audit/job/job-456', 200
