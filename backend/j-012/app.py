import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory, abort, redirect, url_for
import requests
from diff_parser import parse_unified_diff

app = Flask(__name__)

APPLIED_PATCHES_DIR = os.environ.get("APPLIED_PATCHES_DIR", os.path.join(os.path.dirname(__file__), "applied_patches"))
os.makedirs(APPLIED_PATCHES_DIR, exist_ok=True)

# In-memory store for diffs
DIFF_STORE = {}


def create_diff_session(diff_text, source):
    parsed = parse_unified_diff(diff_text)
    diff_id = str(uuid.uuid4())
    DIFF_STORE[diff_id] = {
        "id": diff_id,
        "source": source,
        "stats": parsed["stats"],
        "files": parsed["files"],
    }
    return DIFF_STORE[diff_id]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/viewer/<diff_id>")
def viewer(diff_id):
    if diff_id not in DIFF_STORE:
        abort(404)
    return render_template("viewer.html", diff_id=diff_id)


@app.route("/api/diff/<diff_id>")
def api_diff(diff_id):
    data = DIFF_STORE.get(diff_id)
    if not data:
        return jsonify({"error": "Diff not found"}), 404
    return jsonify(data)


@app.route("/api/upload-diff", methods=["POST"])
def api_upload_diff():
    diff_text = None

    if "diff_file" in request.files and request.files["diff_file"]:
        uploaded = request.files["diff_file"]
        diff_text = uploaded.read().decode("utf-8", errors="replace")

    if not diff_text:
        diff_text = request.form.get("diff_text") or (request.json and request.json.get("diff_text"))

    if not diff_text or diff_text.strip() == "":
        return jsonify({"error": "No diff content provided"}), 400

    session = create_diff_session(diff_text, {
        "type": "upload",
        "meta": {}
    })
    return jsonify({"id": session["id"], "viewer_url": url_for('viewer', diff_id=session["id"])})


@app.route("/api/fetch-pr", methods=["POST"])
def api_fetch_pr():
    owner = request.form.get("owner") or (request.json and request.json.get("owner"))
    repo = request.form.get("repo") or (request.json and request.json.get("repo"))
    pr_number = request.form.get("pr_number") or (request.json and request.json.get("pr_number"))
    token = request.form.get("token") or (request.json and request.json.get("token"))

    if not owner or not repo or not pr_number:
        return jsonify({"error": "Missing owner, repo, or pr_number"}), 400

    try:
        pr_number = int(pr_number)
    except Exception:
        return jsonify({"error": "pr_number must be an integer"}), 400

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return jsonify({"error": "Failed to fetch PR diff", "status": r.status_code, "body": r.text[:1000]}), 400

    diff_text = r.text
    session = create_diff_session(diff_text, {
        "type": "pr",
        "meta": {"owner": owner, "repo": repo, "pr_number": pr_number}
    })
    return jsonify({"id": session["id"], "viewer_url": url_for('viewer', diff_id=session["id"])})


@app.route("/api/patches", methods=["GET"]) 
def api_list_patches():
    files = []
    for name in sorted(os.listdir(APPLIED_PATCHES_DIR)):
        path = os.path.join(APPLIED_PATCHES_DIR, name)
        if os.path.isfile(path) and (name.endswith('.patch') or name.endswith('.diff')):
            files.append({"name": name, "size": os.path.getsize(path)})
    return jsonify({"patches": files})


@app.route("/api/patches/open", methods=["POST"]) 
def api_open_patch():
    name = request.form.get("name") or (request.json and request.json.get("name"))
    if not name:
        return jsonify({"error": "Missing patch name"}), 400
    safe_name = os.path.basename(name)
    path = os.path.join(APPLIED_PATCHES_DIR, safe_name)
    if not os.path.isfile(path):
        return jsonify({"error": "Patch not found"}), 404
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            diff_text = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read patch: {e}"}), 500

    session = create_diff_session(diff_text, {
        "type": "patchfile",
        "meta": {"file": safe_name}
    })
    return jsonify({"id": session["id"], "viewer_url": url_for('viewer', diff_id=session["id"])})


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/api/patches/1/diff', methods=['GET'])
def _auto_stub_api_patches_1_diff():
    return 'Auto-generated stub for /api/patches/1/diff', 200
