import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify

from services.index import IndexRegistry
from services.novelty import score_novelty

app = Flask(__name__)

registry = IndexRegistry()


def load_sample_corpus():
    default_name = "default"
    index = registry.create_index(default_name)
    data_path = os.path.join(os.path.dirname(__file__), "data", "sample_corpus.json")
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                docs = json.load(f)
            index.add_documents(docs)
        except Exception:
            pass
    return default_name


DEFAULT_INDEX = load_sample_corpus()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "indexes": registry.list_indexes()}), 200


@app.route("/api/index/create", methods=["POST"])
def api_index_create():
    body = request.get_json(silent=True) or {}
    name = body.get("name") or "default"
    if name in registry.list_indexes():
        return jsonify({"ok": True, "message": "index exists", "name": name}), 200
    idx = registry.create_index(name)
    return jsonify({"ok": True, "name": idx.name}), 201


@app.route("/api/index/add", methods=["POST"])
def api_index_add():
    body = request.get_json(silent=True) or {}
    name = body.get("index") or DEFAULT_INDEX
    docs = body.get("documents") or []
    if not isinstance(docs, list) or not docs:
        return jsonify({"ok": False, "error": "documents must be a non-empty list"}), 400
    idx = registry.get_index(name)
    if idx is None:
        return jsonify({"ok": False, "error": f"index '{name}' not found"}), 404
    added, total = idx.add_documents(docs)
    return jsonify({"ok": True, "added": added, "total": total, "index": name}), 200


@app.route("/api/score", methods=["POST"])
def api_score():
    body = request.get_json(silent=True) or {}
    name = body.get("index") or DEFAULT_INDEX
    query = body.get("query") or ""
    top_k = int(body.get("top_k") or 5)
    if not query.strip():
        return jsonify({"ok": False, "error": "query is required"}), 400
    idx = registry.get_index(name)
    if idx is None:
        return jsonify({"ok": False, "error": f"index '{name}' not found"}), 404
    result = score_novelty(idx, query, top_k=top_k)
    return jsonify({"ok": True, **result}), 200


@app.route("/api/index/list", methods=["GET"])
def api_index_list():
    names = registry.list_indexes()
    meta = {}
    for n in names:
        idx = registry.get_index(n)
        meta[n] = {
            "documents": idx.count(),
            "vocabulary_size": idx.vocabulary_size(),
        }
    return jsonify({"ok": True, "indexes": meta}), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"ok": False, "error": "not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"ok": False, "error": "internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)



def create_app():
    return app


@app.route('/api/check-novelty', methods=['POST'])
def _auto_stub_api_check_novelty():
    return 'Auto-generated stub for /api/check-novelty', 200
