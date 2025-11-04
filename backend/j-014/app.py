import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify

from db import init_db, get_connection
from scheduler import Scheduler

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize DB and scheduler
init_db()
scheduler = Scheduler()
scheduler.start()


def parse_datetime_local(dt_str):
    if not dt_str:
        return None
    try:
        # HTML datetime-local returns 'YYYY-MM-DDTHH:MM'
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M").isoformat()
    except Exception:
        return None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/jobs/new')
def new_job():
    return render_template('new_job.html')


@app.route('/jobs', methods=['POST'])
def create_job():
    name = request.form.get('name') or 'Untitled Job'
    job_type = request.form.get('type') or 'train_model'
    scheduled_for = parse_datetime_local(request.form.get('start_at'))

    # Collect parameters by job type
    params = {}
    if job_type == 'train_model':
        params['epochs'] = int(request.form.get('epochs') or 10)
        params['epoch_time'] = float(request.form.get('epoch_time') or 0.5)
        params['learning_rate'] = float(request.form.get('learning_rate') or 0.001)
    elif job_type == 'long_task':
        params['steps'] = int(request.form.get('steps') or 20)
        params['step_time'] = float(request.form.get('step_time') or 0.25)
    else:
        params = {k: request.form.get(k) for k in request.form.keys()}

    job_id = scheduler.enqueue_job(name=name, job_type=job_type, params=params, start_at=scheduled_for)
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>')
def job_detail(job_id):
    return render_template('job_detail.html', job_id=job_id)


@app.route('/jobs/<int:job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    scheduler.request_cancel(job_id)
    return redirect(url_for('job_detail', job_id=job_id))


@app.route('/jobs/<int:job_id>/retry', methods=['POST'])
def retry_job(job_id):
    new_id = scheduler.retry_job(job_id)
    return redirect(url_for('job_detail', job_id=new_id))


# JSON APIs
@app.route('/api/jobs')
def api_list_jobs():
    status = request.args.get('status')
    conn = get_connection()
    cur = conn.cursor()
    if status:
        cur.execute('SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC', (status,))
    else:
        cur.execute('SELECT * FROM jobs ORDER BY created_at DESC')
    rows = cur.fetchall()
    conn.close()
    jobs = [dict(row) for row in rows]
    # Decode params JSON
    for j in jobs:
        try:
            j['params'] = json.loads(j['params']) if j.get('params') else {}
        except Exception:
            j['params'] = {}
    return jsonify(jobs)


@app.route('/api/jobs', methods=['POST'])
def api_create_job():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name') or 'Untitled Job'
    job_type = data.get('type') or 'train_model'
    params = data.get('params') or {}
    start_at = data.get('start_at')
    job_id = scheduler.enqueue_job(name=name, job_type=job_type, params=params, start_at=start_at)
    return jsonify({"id": job_id}), 201


@app.route('/api/jobs/<int:job_id>')
def api_job_detail(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
    job = cur.fetchone()
    if not job:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    cur.execute('SELECT * FROM logs WHERE job_id = ? ORDER BY id ASC', (job_id,))
    logs = [dict(r) for r in cur.fetchall()]
    conn.close()

    job_dict = dict(job)
    try:
        job_dict['params'] = json.loads(job_dict['params']) if job_dict.get('params') else {}
    except Exception:
        job_dict['params'] = {}

    job_dict['logs'] = logs
    return jsonify(job_dict)


@app.route('/api/jobs/<int:job_id>/cancel', methods=['POST'])
def api_cancel_job(job_id):
    ok = scheduler.request_cancel(job_id)
    return jsonify({"ok": bool(ok)})


@app.route('/api/jobs/<int:job_id>/retry', methods=['POST'])
def api_retry_job(job_id):
    new_id = scheduler.retry_job(job_id)
    return jsonify({"id": new_id}), 201


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app


@app.route('/api/tasks', methods=['GET', 'POST'])
def _auto_stub_api_tasks():
    return 'Auto-generated stub for /api/tasks', 200
