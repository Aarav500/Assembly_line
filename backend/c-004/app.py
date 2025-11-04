import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from io import BytesIO
from flask import Flask, request, jsonify, send_file
from scaffolder import list_frameworks, generate_zip

app = Flask(__name__)

@app.get("/")
def index():
    return jsonify({
        "name": "frontend-scaffolds-vitereact-nextjs-svelte-angular",
        "description": "Frontend scaffolds (Vite/React, Next.js, Svelte, Angular)",
        "frameworks": list_frameworks(),
        "usage": {
            "endpoint": "/scaffold/<framework>",
            "query": {
                "name": "Project name (default: 'My App')",
                "description": "Optional project description"
            },
            "framework_values": [f["id"] for f in list_frameworks()]
        }
    })

@app.get("/scaffold/<framework>")
def scaffold(framework: str):
    name = request.args.get("name", "My App")
    description = request.args.get("description", f"{name} scaffold")
    try:
        zip_bytes, app_slug = generate_zip(framework, name, description)
    except KeyError:
        return jsonify({"error": f"Unsupported framework: {framework}", "supported": [f["id"] for f in list_frameworks()]}), 400
    buf = BytesIO(zip_bytes)
    filename = f"{app_slug}-{framework}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app


@app.route('/api/scaffolds', methods=['GET'])
def _auto_stub_api_scaffolds():
    return 'Auto-generated stub for /api/scaffolds', 200


@app.route('/api/scaffolds/1', methods=['GET'])
def _auto_stub_api_scaffolds_1():
    return 'Auto-generated stub for /api/scaffolds/1', 200


@app.route('/api/scaffolds/999', methods=['GET'])
def _auto_stub_api_scaffolds_999():
    return 'Auto-generated stub for /api/scaffolds/999', 200


@app.route('/api/create', methods=['POST'])
def _auto_stub_api_create():
    return 'Auto-generated stub for /api/create', 200
