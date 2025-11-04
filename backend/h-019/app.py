import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify, render_template
from indexer import KnowledgeIndex

INDEX_DIR = os.environ.get("INDEX_DIR", "index_data")
DEFAULT_PROJECT_DIR = os.environ.get("PROJECT_DIR", os.getcwd())

app = Flask(__name__)
index = KnowledgeIndex(index_dir=INDEX_DIR)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "has_index": index.is_built(),
        "index_dir": INDEX_DIR
    })

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/build_index", methods=["POST"])
def build_index():
    data = request.get_json(silent=True) or {}
    root_dir = data.get("root_dir", DEFAULT_PROJECT_DIR)
    include = data.get("include", None)
    exclude = data.get("exclude", None)
    try:
        stats = index.build(root_dir=root_dir, include_globs=include, exclude_globs=exclude)
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/query", methods=["POST"])
def query():
    if not index.is_built():
        return jsonify({"ok": False, "error": "Index not built. POST /build_index first."}), 400
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    top_k = int(data.get("top_k", 5))
    if not question:
        return jsonify({"ok": False, "error": "Missing 'question'"}), 400
    try:
        matches = index.search(question, top_k=top_k)
        answer = index.compose_answer(question, matches)
        return jsonify({
            "ok": True,
            "answer": answer,
            "matches": matches
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Auto-build index if none exists
    if not index.is_built():
        try:
            index.build(root_dir=DEFAULT_PROJECT_DIR)
        except Exception:
            pass
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



def create_app():
    return app


@app.route('/topics', methods=['GET'])
def _auto_stub_topics():
    return 'Auto-generated stub for /topics', 200
