import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
import threading
import time
from datetime import datetime
from copy import deepcopy
from flask import Flask, request, jsonify, render_template

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, 'data')
PIPELINES_DIR = os.path.join(DATA_DIR, 'pipelines')

os.makedirs(PIPELINES_DIR, exist_ok=True)

app = Flask(__name__, static_folder='static', template_folder='templates')

RUNS_LOCK = threading.Lock()
RUNS = {}


def now_ts():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def log(run_state, message):
    with RUNS_LOCK:
        run_state['logs'].append(f"[{now_ts()}] {message}")


def save_pipeline_file(pipeline):
    pid = pipeline['id']
    path = os.path.join(PIPELINES_DIR, f"{pid}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(pipeline, f, indent=2)


def load_pipeline_file(pipeline_id):
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_pipelines():
    res = []
    for name in os.listdir(PIPELINES_DIR):
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(PIPELINES_DIR, name), 'r', encoding='utf-8') as f:
                p = json.load(f)
                res.append({'id': p.get('id'), 'name': p.get('name', ''), 'updated_at': p.get('updated_at')})
        except Exception:
            continue
    return sorted(res, key=lambda x: x.get('updated_at') or '', reverse=True)


def build_graph(pipeline):
    nodes = {n['id']: n for n in pipeline.get('nodes', [])}
    edges = pipeline.get('edges', [])
    children = {nid: [] for nid in nodes}
    parents = {nid: [] for nid in nodes}
    for e in edges:
        s = e.get('source')
        t = e.get('target')
        if s in nodes and t in nodes:
            children[s].append(t)
            parents[t].append(s)
    return nodes, children, parents


def get_start_nodes(nodes, parents):
    starts = [nid for nid, n in nodes.items() if n.get('type') == 'start']
    if starts:
        return starts
    # Fallback: nodes with no parents
    return [nid for nid in nodes if len(parents.get(nid, [])) == 0]


def new_run(pipeline_id):
    run_id = uuid.uuid4().hex
    run_state = {
        'id': run_id,
        'pipeline_id': pipeline_id,
        'status': 'running',
        'logs': [],
        'created_at': now_ts(),
        'updated_at': now_ts(),
        'waiting_node_id': None,
        'data_per_node': {},
    }
    with RUNS_LOCK:
        RUNS[run_id] = run_state
    return run_id, run_state


def set_waiting(run_state, node_id, before_payload):
    with RUNS_LOCK:
        run_state['status'] = 'waiting'
        run_state['waiting_node_id'] = node_id
        run_state['updated_at'] = now_ts()
        run_state['data_per_node'].setdefault(node_id, {})['before'] = before_payload


def set_running(run_state):
    with RUNS_LOCK:
        run_state['status'] = 'running'
        run_state['waiting_node_id'] = None
        run_state['updated_at'] = now_ts()


def set_completed(run_state):
    with RUNS_LOCK:
        run_state['status'] = 'completed'
        run_state['updated_at'] = now_ts()


def set_failed(run_state, err):
    with RUNS_LOCK:
        run_state['status'] = 'failed'
        run_state['updated_at'] = now_ts()
    log(run_state, f"ERROR: {err}")


def node_process(node, in_payload, run_state, webhook_payload=None):
    ntype = node.get('type')
    cfg = node.get('config') or {}
    # Ensure dict payload
    payload = deepcopy(in_payload) if isinstance(in_payload, dict) else {'input': in_payload}

    if ntype == 'start':
        initial = cfg.get('initial_payload')
        if isinstance(initial, dict):
            payload = deepcopy(initial)
        else:
            # try parse JSON string if given
            if isinstance(initial, str) and initial.strip():
                try:
                    payload = json.loads(initial)
                except Exception:
                    payload = {'initial': initial}
            else:
                payload = {}
        log(run_state, f"Start node initialized payload: {payload}")
        return payload, None

    if ntype == 'agent-echo':
        prompt = cfg.get('prompt', '')
        out = deepcopy(payload)
        out['message'] = f"{prompt}{payload}"
        log(run_state, f"agent-echo produced: {out}")
        return out, None

    if ntype == 'agent-uppercase':
        out = deepcopy(payload)
        if 'text' in out and isinstance(out['text'], str):
            out['text'] = out['text'].upper()
        elif 'message' in out and isinstance(out['message'], str):
            out['message'] = out['message'].upper()
        log(run_state, f"agent-uppercase produced: {out}")
        return out, None

    if ntype == 'transform-add-field':
        key = cfg.get('key', 'added')
        value = cfg.get('value', '')
        out = deepcopy(payload)
        out[key] = value
        log(run_state, f"transform-add-field added {key}={value}")
        return out, None

    if ntype == 'webhook':
        # If webhook_payload provided, merge and continue; else wait
        if webhook_payload is None:
            return None, 'WAIT'
        out = deepcopy(payload)
        out['webhook'] = webhook_payload
        log(run_state, f"webhook resumed with payload: {webhook_payload}")
        return out, None

    if ntype == 'end':
        log(run_state, f"Reached end node. Final payload: {payload}")
        return payload, 'END'

    # default passthrough
    log(run_state, f"Passthrough node type={ntype}")
    return payload, None


def execute_pipeline(run_state, pipeline, start_node_ids=None, initial_payload=None, resume_from=None, webhook_payload=None):
    nodes, children, parents = build_graph(pipeline)
    visited = set()

    def _walk(node_id, in_payload):
        if node_id in visited:
            log(run_state, f"Detected cycle at node {node_id}. Aborting this path.")
            return 'CYCLE'
        visited.add(node_id)

        node = nodes.get(node_id)
        if not node:
            log(run_state, f"Node {node_id} missing.")
            return 'ERROR'

        log(run_state, f"Entering node {node_id} ({node.get('type')})")

        # process node
        try:
            if resume_from == node_id:
                out_payload, special = node_process(node, in_payload, run_state, webhook_payload=webhook_payload)
            else:
                out_payload, special = node_process(node, in_payload, run_state)
        except Exception as e:
            set_failed(run_state, f"Exception in node {node_id}: {e}")
            return 'ERROR'

        # handle special states
        if special == 'WAIT':
            set_waiting(run_state, node_id, in_payload)
            log(run_state, f"Pipeline waiting for webhook at node {node_id}")
            return 'WAIT'
        if special == 'END':
            return 'END'

        # propagate to children
        for child_id in children.get(node_id, []):
            res = _walk(child_id, out_payload)
            if res in ('WAIT', 'ERROR'):
                return res
        return 'OK'

    try:
        if resume_from:
            # resume path from specific node
            res = _walk(resume_from, initial_payload)
            if res == 'WAIT':
                return
            if res == 'ERROR':
                return
            set_completed(run_state)
            log(run_state, "Pipeline completed (resumed run).")
            return

        starts = start_node_ids or get_start_nodes(nodes, parents)
        payload = deepcopy(initial_payload) if initial_payload is not None else {}
        if not starts:
            set_failed(run_state, "No start node(s) found.")
            return
        for sid in starts:
            res = _walk(sid, payload)
            if res == 'WAIT':
                return
            if res == 'ERROR':
                set_failed(run_state, f"Error during execution starting at {sid}")
                return
        set_completed(run_state)
        log(run_state, "Pipeline completed.")
    except Exception as e:
        set_failed(run_state, f"Unhandled exception: {e}")


def start_run_thread(run_state, pipeline, initial_payload=None):
    t = threading.Thread(target=execute_pipeline, args=(run_state, pipeline, None, initial_payload), daemon=True)
    t.start()


def resume_run_thread(run_state, pipeline, node_id, webhook_payload):
    # Use stored 'before' payload for this node
    before = run_state['data_per_node'].get(node_id, {}).get('before', {})
    set_running(run_state)
    t = threading.Thread(target=execute_pipeline, args=(run_state, pipeline, None, before, node_id, webhook_payload), daemon=True)
    t.start()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/pipelines', methods=['GET'])
def api_list_pipelines():
    return jsonify({'pipelines': list_pipelines()})


@app.route('/api/pipelines', methods=['POST'])
def api_create_pipeline():
    data = request.get_json(force=True, silent=True) or {}
    pid = uuid.uuid4().hex
    pipeline = {
        'id': pid,
        'name': data.get('name') or f"Pipeline {pid[:6]}",
        'nodes': data.get('nodes') or [],
        'edges': data.get('edges') or [],
        'created_at': now_ts(),
        'updated_at': now_ts(),
    }
    save_pipeline_file(pipeline)
    return jsonify({'pipeline': pipeline})


@app.route('/api/pipelines/<pipeline_id>', methods=['GET'])
def api_get_pipeline(pipeline_id):
    p = load_pipeline_file(pipeline_id)
    if not p:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({'pipeline': p})


@app.route('/api/pipelines/<pipeline_id>', methods=['PUT'])
def api_update_pipeline(pipeline_id):
    p = load_pipeline_file(pipeline_id)
    if not p:
        return jsonify({'error': 'not_found'}), 404
    data = request.get_json(force=True, silent=True) or {}
    p['name'] = data.get('name', p.get('name'))
    p['nodes'] = data.get('nodes', p.get('nodes'))
    p['edges'] = data.get('edges', p.get('edges'))
    p['updated_at'] = now_ts()
    save_pipeline_file(p)
    return jsonify({'pipeline': p})


@app.route('/api/pipelines/<pipeline_id>', methods=['DELETE'])
def api_delete_pipeline(pipeline_id):
    path = os.path.join(PIPELINES_DIR, f"{pipeline_id}.json")
    if not os.path.exists(path):
        return jsonify({'error': 'not_found'}), 404
    os.remove(path)
    return jsonify({'ok': True})


@app.route('/api/pipelines/<pipeline_id>/run', methods=['POST'])
def api_run_pipeline(pipeline_id):
    p = load_pipeline_file(pipeline_id)
    if not p:
        return jsonify({'error': 'not_found'}), 404
    data = request.get_json(force=True, silent=True) or {}
    initial_payload = data.get('payload')
    run_id, run_state = new_run(pipeline_id)
    log(run_state, f"Run {run_id} started for pipeline {pipeline_id}")
    start_run_thread(run_state, p, initial_payload)
    return jsonify({'run_id': run_id})


@app.route('/api/runs/<run_id>', methods=['GET'])
def api_get_run(run_id):
    with RUNS_LOCK:
        run_state = RUNS.get(run_id)
    if not run_state:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({
        'id': run_state['id'],
        'pipeline_id': run_state['pipeline_id'],
        'status': run_state['status'],
        'waiting_node_id': run_state['waiting_node_id'],
        'logs': run_state['logs'],
        'updated_at': run_state['updated_at'],
    })


@app.route('/webhook/<pipeline_id>/<node_id>', methods=['POST'])
def webhook_trigger(pipeline_id, node_id):
    payload = request.get_json(force=True, silent=True) or {}
    # find a waiting run for this pipeline and node
    target_run = None
    with RUNS_LOCK:
        for r in RUNS.values():
            if r['pipeline_id'] == pipeline_id and r['status'] == 'waiting' and r['waiting_node_id'] == node_id:
                target_run = r
                break
    if not target_run:
        # Optionally, start a new run that begins at this node (advanced). For simplicity, return 404.
        return jsonify({'error': 'no_waiting_run', 'message': 'No run is waiting at this webhook'}), 404

    pipeline = load_pipeline_file(pipeline_id)
    if not pipeline:
        return jsonify({'error': 'pipeline_not_found'}), 404

    log(target_run, f"Webhook received at node {node_id} with payload: {payload}")
    resume_run_thread(target_run, pipeline, node_id, payload)
    return jsonify({'ok': True, 'run_id': target_run['id']})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
