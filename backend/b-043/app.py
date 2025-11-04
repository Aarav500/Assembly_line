import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from flask import Flask, render_template, abort, redirect, url_for, jsonify

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'flows.json')


def load_flows():
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        flows = {f['id']: f for f in data.get('flows', [])}
        return flows


def get_flow(flow_id):
    flows = load_flows()
    return flows.get(flow_id)


def get_screen(flow, screen_id):
    for s in flow.get('screens', []):
        if s.get('id') == screen_id:
            return s
    return None


@app.route('/')
def index():
    flows = load_flows()
    return render_template('index.html', flows=list(flows.values()))


@app.route('/flow/<flow_id>')
def flow_entry(flow_id):
    flow = get_flow(flow_id)
    if not flow:
        abort(404)
    start_screen = flow.get('start_screen')
    if not start_screen:
        abort(404)
    return redirect(url_for('flow_screen', flow_id=flow_id, screen_id=start_screen))


@app.route('/flow/<flow_id>/screen/<screen_id>')
def flow_screen(flow_id, screen_id):
    flow = get_flow(flow_id)
    if not flow:
        abort(404)
    screen = get_screen(flow, screen_id)
    if not screen:
        abort(404)
    # Build screen map for quick existence checks
    screen_ids = {s['id'] for s in flow.get('screens', [])}
    return render_template('flow.html', flow=flow, screen=screen, screen_ids=screen_ids)


# Simple APIs to integrate with front-end tooling if needed
@app.route('/api/flows')
def api_flows():
    return jsonify(list(load_flows().values()))


@app.route('/api/flow/<flow_id>')
def api_flow(flow_id):
    flow = get_flow(flow_id)
    if not flow:
        abort(404)
    return jsonify(flow)


if __name__ == '__main__':
    app.run(debug=True)


def create_app():
    return app


@app.route('/flow/start', methods=['GET'])
def _auto_stub_flow_start():
    return 'Auto-generated stub for /flow/start', 200


@app.route('/flow/step3', methods=['GET'])
def _auto_stub_flow_step3():
    return 'Auto-generated stub for /flow/step3', 200
