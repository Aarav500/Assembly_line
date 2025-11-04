import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from search.indexer import Indexer
from search.utils import scan_paths

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

indexer = Indexer()
indexer.load()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "docs": len(indexer.docs), "embeddings": indexer.emb_ready})

@app.route("/stats", methods=["GET"])
def stats():
    return jsonify(indexer.stats())

@app.route("/doc/<doc_id>", methods=["GET"])
def get_doc(doc_id):
    doc = indexer.get_doc(doc_id)
    if not doc:
        return jsonify({"error": "not_found"}), 404
    return jsonify(doc)

@app.route("/index/bulk", methods=["POST"])
def index_bulk():
    payload = request.get_json(force=True, silent=True) or {}
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400

    added = indexer.add_documents(items)
    # Rebuild lexical always for consistency; embeddings incrementally
    indexer.rebuild_lexical()
    indexer.ensure_embeddings(new_only=True)
    indexer.save()
    return jsonify({"added": added, "total": len(indexer.docs)})

@app.route("/index/scan", methods=["POST"])
def index_scan():
    payload = request.get_json(force=True, silent=True) or {}
    roots = payload.get("roots") or []
    include_globs = payload.get("include_globs")
    exclude_globs = payload.get("exclude_globs")
    if not roots:
        return jsonify({"error": "roots is required"}), 400

    scanned = scan_paths(roots, include_globs=include_globs, exclude_globs=exclude_globs)
    added = indexer.add_documents(scanned)
    indexer.rebuild_lexical()
    indexer.ensure_embeddings(new_only=True)
    indexer.save()
    return jsonify({"scanned": len(scanned), "added": added, "total": len(indexer.docs)})

@app.route("/index/clear", methods=["POST"]) 
def clear_index():
    indexer.clear()
    indexer.save()
    return jsonify({"cleared": True})

@app.route("/search", methods=["GET"]) 
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q is required"}), 400
    try:
        top_k = int(request.args.get("top_k", 10))
    except ValueError:
        top_k = 10
    mode = request.args.get("mode", "hybrid")
    w_lex = float(request.args.get("w_lex", 0.5))
    w_sem = float(request.args.get("w_sem", 0.5))
    source_types = request.args.get("types")  # comma-separated filter
    if source_types:
        source_types = [t.strip() for t in source_types.split(",") if t.strip()]

    res = indexer.search(q, top_k=top_k, mode=mode, w_lex=w_lex, w_sem=w_sem, source_types=source_types)
    return jsonify(res)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/documents', methods=['GET'])
def _auto_stub_documents():
    return 'Auto-generated stub for /documents', 200
