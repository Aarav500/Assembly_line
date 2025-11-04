import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from services.mindmap_parser import mindmap_to_manifest
from services.manifest_utils import pretty_json, validate_manifest_text
from services.scaffolder import scaffold_project_zip

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

@app.route("/")
def index():
    return redirect(url_for("mindmap"))

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("mindmap"))

@app.route("/mindmap", methods=["GET", "POST"])
def mindmap():
    error = None
    warnings = []
    default_mindmap = None
    if request.method == "GET":
        mindmap_text = session.get("mindmap_text")
        if not mindmap_text:
            # load example
            try:
                with open(os.path.join("examples", "sample.mindmap.txt"), "r", encoding="utf-8") as f:
                    default_mindmap = f.read()
            except Exception:
                default_mindmap = "Project: MyApp\n  Pages\n    Home\n    About\n  Models\n    User: id:int, name:str\n  APIs\n    GET /api/users\n    POST /api/users\n"
        return render_template("mindmap.html", mindmap_text=mindmap_text or default_mindmap, error=error, warnings=warnings)

    # POST: parse mindmap to manifest
    mindmap_text = request.form.get("mindmap_text", "").strip()
    session["mindmap_text"] = mindmap_text
    try:
        manifest, warnings = mindmap_to_manifest(mindmap_text)
        manifest_json = pretty_json(manifest)
        session["manifest_json"] = manifest_json
        session["warnings"] = warnings
        return redirect(url_for("manifest"))
    except Exception as e:
        error = str(e)
        return render_template("mindmap.html", mindmap_text=mindmap_text, error=error, warnings=warnings), 400

@app.route("/manifest", methods=["GET", "POST"])
def manifest():
    if request.method == "GET":
        manifest_json = session.get("manifest_json")
        if not manifest_json:
            return redirect(url_for("mindmap"))
        warnings = session.get("warnings", [])
        return render_template("manifest.html", manifest_json=manifest_json, warnings=warnings)

    action = request.form.get("action")
    manifest_text = request.form.get("manifest_json", "").strip()
    try:
        manifest = validate_manifest_text(manifest_text)
        manifest_json = pretty_json(manifest)
        session["manifest_json"] = manifest_json
    except Exception as e:
        warnings = session.get("warnings", [])
        return render_template("manifest.html", manifest_json=manifest_text, warnings=warnings, error=str(e)), 400

    if action == "download":
        return redirect(url_for("scaffold"))
    else:
        warnings = session.get("warnings", [])
        return render_template("manifest.html", manifest_json=manifest_json, warnings=warnings)

@app.route("/scaffold", methods=["GET", "POST"])
def scaffold():
    manifest_json = session.get("manifest_json")
    if not manifest_json:
        return redirect(url_for("mindmap"))
    try:
        manifest = json.loads(manifest_json)
        zip_path, zip_name = scaffold_project_zip(manifest)
        return send_file(zip_path, as_attachment=True, download_name=zip_name)
    except Exception as e:
        return render_template("manifest.html", manifest_json=manifest_json, warnings=session.get("warnings", []), error=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)



def create_app():
    return app


@app.route('/api/parse-mindmap', methods=['POST'])
def _auto_stub_api_parse_mindmap():
    return 'Auto-generated stub for /api/parse-mindmap', 200


@app.route('/api/generate-manifest', methods=['POST'])
def _auto_stub_api_generate_manifest():
    return 'Auto-generated stub for /api/generate-manifest', 200
