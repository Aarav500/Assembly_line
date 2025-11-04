from flask import Blueprint, request, jsonify
from caching import cache_response


search_bp = Blueprint("search", __name__)

# Demo dataset
DATASET = [
    {"id": 1, "title": "Flask Web Development"},
    {"id": 2, "title": "Python Crash Course"},
    {"id": 3, "title": "Effective Python"},
    {"id": 4, "title": "Fluent Python"},
]


@search_bp.route("/search")
@cache_response(timeout=15)
def search():
    try:
        q = request.args.get("q", "").strip().lower()
        results = []
        if q:
            results = [item for item in DATASET if q in item["title"].lower()]
        return jsonify({"query": q, "results": results})
    except AttributeError as e:
        return jsonify({"error": "Invalid query parameter", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "An error occurred during search", "details": str(e)}), 500