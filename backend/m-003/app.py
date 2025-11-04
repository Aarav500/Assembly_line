import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify

from reviewers import SuggestionEngine

app = Flask(__name__)


def parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})


@app.route("/suggest-reviewers", methods=["POST"]) 
def suggest_reviewers():
    try:
        payload = request.get_json(silent=True) or {}
        changed_files = payload.get("changed_files") or []
        if not isinstance(changed_files, list) or not all(isinstance(p, str) for p in changed_files):
            return jsonify({"error": "changed_files must be a list of file paths"}), 400

        repo_path = payload.get("repo_path") or os.getcwd()
        limit = payload.get("limit") or 5
        author = payload.get("author")
        include_teams = parse_bool(payload.get("include_teams"), default=False)
        use_git_history = parse_bool(payload.get("git_history"), default=False)
        teams_path = payload.get("teams_path")  # optional override

        engine = SuggestionEngine(repo_path=repo_path, teams_path=teams_path)
        result = engine.suggest(
            changed_files=changed_files,
            limit=int(limit),
            author=author,
            include_teams=include_teams,
            use_git_history=use_git_history,
        )
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Error generating suggestions")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/reset', methods=['POST'])
def _auto_stub_reset():
    return 'Auto-generated stub for /reset', 200


@app.route('/commits', methods=['POST'])
def _auto_stub_commits():
    return 'Auto-generated stub for /commits', 200


@app.route('/reviewers', methods=['POST'])
def _auto_stub_reviewers():
    return 'Auto-generated stub for /reviewers', 200
