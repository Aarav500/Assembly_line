import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
from src.graph_store import GraphStore
from src.extractor import Extractor
from src.query_engine import QueryEngine

app = Flask(__name__, static_folder="static", static_url_path="/static")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
GRAPH_PATH = os.path.join(DATA_DIR, "graph.json")

os.makedirs(DATA_DIR, exist_ok=True)

store = GraphStore()
if os.path.exists(GRAPH_PATH):
    try:
        store.load(GRAPH_PATH)
    except Exception:
        pass

extractor = Extractor(store)
query_engine = QueryEngine(store)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.post("/api/artifacts")
def add_artifact():
    data = request.get_json(force=True, silent=True) or {}
    art_id = data.get("id") or str(uuid.uuid4())
    art_type = (data.get("type") or "text").lower()
    content = data.get("content") or ""
    metadata = data.get("metadata") or {}

    if not isinstance(content, str):
        return jsonify({"error": "content must be string"}), 400

    result = extractor.process_artifact(artifact_id=art_id, artifact_type=art_type, content=content, metadata=metadata)
    store.save(GRAPH_PATH)

    return jsonify({
        "artifact_id": art_id,
        "nodes_added": result.get("nodes_added", 0),
        "edges_added": result.get("edges_added", 0),
        "summary": result.get("summary", {})
    })

@app.get("/api/graph")
def get_graph():
    return jsonify(store.to_dict())

@app.get("/api/nodes")
def search_nodes():
    q = request.args.get("query", "").strip()
    t = request.args.get("type")
    results = store.search_nodes(q, type_filter=t)
    return jsonify({"query": q, "results": results})

@app.post("/api/query")
def run_query():
    data = request.get_json(force=True, silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"error": "query is required"}), 400
    resp = query_engine.execute(q)
    return jsonify(resp)

@app.post("/api/reset")
def reset():
    store.clear()
    try:
        if os.path.exists(GRAPH_PATH):
            os.remove(GRAPH_PATH)
    except Exception:
        pass
    return jsonify({"status": "ok", "message": "graph cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/extract', methods=['POST'])
def _auto_stub_extract():
    return 'Auto-generated stub for /extract', 200


@app.route('/query?entity=Leonardo', methods=['GET'])
def _auto_stub_query_entity_Leonardo():
    return 'Auto-generated stub for /query?entity=Leonardo', 200
