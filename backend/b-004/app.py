import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, jsonify, request, render_template, send_from_directory
from idea_engine.library import IdeaLibrary
from idea_engine.utils import ValidationError

app = Flask(__name__)

DATA_PATH = os.environ.get("IDEA_LIBRARY_PATH", os.path.join(os.path.dirname(__file__), "data", "templates.json"))
library = IdeaLibrary.from_file(DATA_PATH)

@app.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({"error": "validation_error", "message": str(err), "details": err.details}), 400

@app.errorhandler(404)
def handle_not_found(err):
    return jsonify({"error": "not_found", "message": "Resource not found"}), 404

@app.errorhandler(400)
def handle_bad_request(err):
    return jsonify({"error": "bad_request", "message": getattr(err, "description", "Bad request")}), 400

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, "static"), filename)

@app.route("/api/categories", methods=["GET"])
def list_categories():
    cats = library.categories()
    return jsonify({"categories": cats})

@app.route("/api/templates", methods=["GET"])
def list_templates():
    category = request.args.get("category")
    q = request.args.get("q")
    templates = library.search(category=category, query=q)
    return jsonify({"templates": [t.to_dict(summary=True) for t in templates]})

@app.route("/api/templates/<template_id>", methods=["GET"])
def get_template(template_id):
    t = library.get(template_id)
    if not t:
        return jsonify({"error": "not_found", "message": f"Template '{template_id}' not found"}), 404
    return jsonify({"template": t.to_dict()})

@app.route("/api/render", methods=["POST"])
def render_template_api():
    payload = request.get_json(silent=True) or {}
    template_id = payload.get("template_id")
    inputs = payload.get("inputs", {})
    fmt = payload.get("format", "markdown")

    t = library.get(template_id)
    if not t:
        return jsonify({"error": "not_found", "message": f"Template '{template_id}' not found"}), 404

    rendered = library.render(template_id, inputs=inputs, output_format=fmt)
    return jsonify({
        "template_id": template_id,
        "format": fmt,
        "sections": rendered["sections"],
        "combined": rendered["combined"],
        "meta": rendered["meta"],
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app
