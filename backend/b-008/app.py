import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, render_template
from idea_ranker.ranking import rank_ideas, DEFAULT_WEIGHTS


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/health", methods=["GET"]) 
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/rank", methods=["POST"]) 
    def api_rank():
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400
        if not payload or "ideas" not in payload or not isinstance(payload["ideas"], list):
            return jsonify({"error": "Payload must include 'ideas' as a list"}), 400

        ideas = payload["ideas"]
        weights = payload.get("weights") or DEFAULT_WEIGHTS

        # Validate idea items
        normalized_ideas = []
        for i, idea in enumerate(ideas):
            if not isinstance(idea, dict):
                return jsonify({"error": f"Idea at index {i} must be an object with 'title' and/or 'description'"}), 400
            title = (idea.get("title") or "").strip()
            description = (idea.get("description") or "").strip()
            if not title and not description:
                return jsonify({"error": f"Idea at index {i} must have at least a title or description"}), 400
            normalized_ideas.append({"title": title, "description": description})

        try:
            result = rank_ideas(normalized_ideas, weights=weights)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify(result)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)



@app.route('/ideas', methods=['GET', 'POST'])
def _auto_stub_ideas():
    return 'Auto-generated stub for /ideas', 200
