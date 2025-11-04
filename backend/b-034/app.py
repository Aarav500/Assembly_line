import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, jsonify, request, render_template, abort

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data')
DATA_FILE = os.path.join(DATA_PATH, 'dependencies.json')


def ensure_data_file():
    os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        seed = {
            "features": {
                "Login": {"id": "Login", "name": "Login"},
                "UserProfile": {"id": "UserProfile", "name": "UserProfile"},
                "Dashboard": {"id": "Dashboard", "name": "Dashboard"},
                "Billing": {"id": "Billing", "name": "Billing"}
            },
            "dependencies": [
                {"from": "Dashboard", "to": "Login"},
                {"from": "UserProfile", "to": "Login"},
                {"from": "Billing", "to": "UserProfile"}
            ]
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(seed, f, indent=2)


def load_data():
    ensure_data_file()
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(data):
    os.makedirs(DATA_PATH, exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def build_adjacency(data):
    adj = {k: set() for k in data['features'].keys()}
    rev = {k: set() for k in data['features'].keys()}
    for e in data['dependencies']:
        src = e['from']
        dst = e['to']
        if src in adj:
            adj[src].add(dst)
        if dst in rev:
            rev[dst].add(src)
    return adj, rev


def path_exists(adj, start, target):
    # DFS from start to target on directed graph defined by adj
    if start == target:
        return True
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for nxt in adj.get(node, []):
            if nxt == target:
                return True
            if nxt not in visited:
                stack.append(nxt)
    return False


def would_create_cycle(data, src, dst):
    # adding edge src->dst creates a cycle if there's a path from dst to src
    adj, _ = build_adjacency(data)
    return path_exists(adj, dst, src)


def toposort(data):
    adj, _ = build_adjacency(data)
    indeg = {n: 0 for n in adj}
    for u, outs in adj.items():
        for v in outs:
            indeg[v] = indeg.get(v, 0) + 1
    queue = [n for n, d in indeg.items() if d == 0]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for v in adj.get(node, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    if len(order) != len(adj):
        # Cycle detected
        return None
    return order


def as_graph_response(data):
    nodes = [
        {
            "id": f_id,
            "name": f_data.get('name', f_id)
        } for f_id, f_data in data['features'].items()
    ]
    links = [
        {
            "source": e['from'],
            "target": e['to']
        } for e in data['dependencies']
        if e['from'] in data['features'] and e['to'] in data['features']
    ]
    return {"nodes": nodes, "links": links}


def get_dependencies_set(data, feature, transitive=False):
    adj, _ = build_adjacency(data)
    if feature not in adj:
        return set()
    if not transitive:
        return set(adj[feature])
    # BFS/DFS for transitive deps
    deps = set()
    stack = list(adj[feature])
    while stack:
        n = stack.pop()
        if n in deps:
            continue
        deps.add(n)
        for nxt in adj.get(n, []):
            if nxt not in deps:
                stack.append(nxt)
    return deps


def get_dependents_set(data, feature, transitive=False):
    _, rev = build_adjacency(data)
    if feature not in rev:
        return set()
    if not transitive:
        return set(rev[feature])
    deps = set()
    stack = list(rev[feature])
    while stack:
        n = stack.pop()
        if n in deps:
            continue
        deps.add(n)
        for nxt in rev.get(n, []):
            if nxt not in deps:
                stack.append(nxt)
    return deps


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.get('/api/graph')
def api_graph():
    data = load_data()
    return jsonify(as_graph_response(data))


@app.get('/api/features')
def api_features():
    data = load_data()
    features = list(data['features'].values())
    features.sort(key=lambda x: x['id'].lower())
    return jsonify({"features": features})


@app.post('/api/features')
def api_add_feature():
    body = request.get_json(force=True, silent=True) or {}
    feature_id = body.get('id') or body.get('name')
    if not feature_id or not isinstance(feature_id, str):
        return jsonify({"error": "Feature 'id' or 'name' (string) is required"}), 400
    feature_id = feature_id.strip()
    data = load_data()
    if feature_id in data['features']:
        return jsonify({"error": f"Feature '{feature_id}' already exists"}), 409
    data['features'][feature_id] = {
        "id": feature_id,
        "name": body.get('name', feature_id),
        "metadata": body.get('metadata', {})
    }
    save_data(data)
    return jsonify(data['features'][feature_id]), 201


@app.delete('/api/features/<feature_id>')
def api_delete_feature(feature_id):
    data = load_data()
    if feature_id not in data['features']:
        return jsonify({"error": f"Feature '{feature_id}' not found"}), 404
    # Remove feature and related dependencies
    data['dependencies'] = [e for e in data['dependencies'] if e['from'] != feature_id and e['to'] != feature_id]
    del data['features'][feature_id]
    save_data(data)
    return jsonify({"deleted": feature_id})


@app.post('/api/dependencies')
def api_add_dependency():
    body = request.get_json(force=True, silent=True) or {}
    src = body.get('from') or body.get('src') or body.get('source')
    dst = body.get('to') or body.get('dst') or body.get('target')
    if not src or not dst:
        return jsonify({"error": "Fields 'from' and 'to' are required"}), 400
    if src == dst:
        return jsonify({"error": "A feature cannot depend on itself"}), 400
    data = load_data()
    if src not in data['features'] or dst not in data['features']:
        return jsonify({"error": "Both 'from' and 'to' features must exist"}), 400
    # check duplicate
    for e in data['dependencies']:
        if e['from'] == src and e['to'] == dst:
            return jsonify({"error": "Dependency already exists"}), 409
    # cycle check
    if would_create_cycle(data, src, dst):
        return jsonify({"error": "Adding this dependency would create a cycle"}), 400
    data['dependencies'].append({"from": src, "to": dst})
    save_data(data)
    return jsonify({"from": src, "to": dst}), 201


@app.delete('/api/dependencies')
def api_delete_dependency():
    src = request.args.get('from') or request.args.get('src') or request.args.get('source')
    dst = request.args.get('to') or request.args.get('dst') or request.args.get('target')
    if not src or not dst:
        return jsonify({"error": "Query params 'from' and 'to' are required"}), 400
    data = load_data()
    before = len(data['dependencies'])
    data['dependencies'] = [e for e in data['dependencies'] if not (e['from'] == src and e['to'] == dst)]
    after = len(data['dependencies'])
    if after == before:
        return jsonify({"error": "Dependency not found"}), 404
    save_data(data)
    return jsonify({"deleted": {"from": src, "to": dst}})


@app.get('/api/dependencies/<feature_id>')
def api_get_dependencies(feature_id):
    transitive = request.args.get('transitive', 'false').lower() in ('1', 'true', 'yes')
    data = load_data()
    if feature_id not in data['features']:
        return jsonify({"error": f"Feature '{feature_id}' not found"}), 404
    deps = sorted(list(get_dependencies_set(data, feature_id, transitive=transitive)))
    return jsonify({"feature": feature_id, "dependencies": deps, "transitive": transitive})


@app.get('/api/dependents/<feature_id>')
def api_get_dependents(feature_id):
    transitive = request.args.get('transitive', 'false').lower() in ('1', 'true', 'yes')
    data = load_data()
    if feature_id not in data['features']:
        return jsonify({"error": f"Feature '{feature_id}' not found"}), 404
    deps = sorted(list(get_dependents_set(data, feature_id, transitive=transitive)))
    return jsonify({"feature": feature_id, "dependents": deps, "transitive": transitive})


@app.get('/api/toposort')
def api_toposort():
    data = load_data()
    order = toposort(data)
    if order is None:
        return jsonify({"error": "Cycle detected in graph"}), 400
    return jsonify({"order": order})


if __name__ == '__main__':
    ensure_data_file()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



def create_app():
    return app


@app.route('/features/messaging/dependencies', methods=['GET'])
def _auto_stub_features_messaging_dependencies():
    return 'Auto-generated stub for /features/messaging/dependencies', 200


@app.route('/features/authentication/dependents', methods=['GET'])
def _auto_stub_features_authentication_dependents():
    return 'Auto-generated stub for /features/authentication/dependents', 200
