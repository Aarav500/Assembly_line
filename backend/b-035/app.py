import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import json
from flask import Flask, request, jsonify, render_template

from reuse.indexer import CorpusIndex
from reuse.matcher import IdeaMatcher
from reuse.utils import load_config


def create_app():
    app = Flask(__name__)

    config_path = os.environ.get("REUSE_CONFIG", "config.yaml")
    cfg = load_config(config_path)

    index_lock = threading.Lock()
    corpus_index = CorpusIndex(cfg)

    def ensure_index():
        if not corpus_index.is_ready:
            with index_lock:
                if not corpus_index.is_ready:
                    corpus_index.build()

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/api/match", methods=["POST"])
    def api_match():
        ensure_index()
        payload = request.get_json(silent=True) or {}
        idea = (payload.get("idea") or "").strip()
        top_k = int(payload.get("top_k") or 5)
        if not idea:
            return jsonify({"error": "Missing 'idea'"}), 400
        matcher = IdeaMatcher(corpus_index)
        parts = matcher.split_idea(idea)
        results = []
        for part in parts:
            matches = matcher.match_part(part, top_k=top_k)
            results.append({
                "part": part,
                "matches": [m.to_dict() for m in matches]
            })
        return jsonify({
            "parts": results,
            "stats": corpus_index.stats()
        })

    @app.route("/api/reindex", methods=["POST", "GET"])
    def api_reindex():
        with index_lock:
            corpus_index.build(force=True)
        return jsonify({"status": "reindexed", "stats": corpus_index.stats()})

    @app.route("/api/artifact/<artifact_id>")
    def api_artifact(artifact_id):
        ensure_index()
        art = corpus_index.get_artifact_by_id(artifact_id)
        if not art:
            return jsonify({"error": "not found"}), 404
        return jsonify(art.to_dict(include_content=True))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



@app.route('/api/blueprints', methods=['GET'])
def _auto_stub_api_blueprints():
    return 'Auto-generated stub for /api/blueprints', 200
