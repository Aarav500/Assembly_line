import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from idea_gen.generator import IdeaGenerator

app = Flask(__name__)

generator = IdeaGenerator()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/generate-ideas")
def generate_ideas():
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Field 'topic' is required and must be a non-empty string."}), 400

    try:
        count = int(data.get("count", 50))
    except Exception:
        return jsonify({"error": "Field 'count' must be an integer."}), 400

    if count < 1:
        return jsonify({"error": "Field 'count' must be >= 1."}), 400

    constraints = data.get("constraints") or {}
    seed = data.get("seed")

    try:
        result = generator.generate(topic=topic, count=count, constraints=constraints, seed=seed)
    except Exception as e:
        return jsonify({"error": f"Generation failed: {e}"}), 500

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)



def create_app():
    return app
