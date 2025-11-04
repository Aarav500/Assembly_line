import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
from flask import Flask, render_template, request, send_file, jsonify
from services.generator import generate_project_zip
from utils.slugify import slugify

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"]) 
def generate():
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        form = request.form
        data = {
            "project_name": form.get("project_name", "my-project"),
            "description": form.get("description", ""),
            "author": form.get("author", ""),
            "license": form.get("license", "MIT"),
            "package_name": form.get("package_name"),
            "python_version": form.get("python_version", "3.11"),
            "ci_provider": form.get("ci_provider", "github"),
            "include_docker": form.get("include_docker", "true") == "true",
            "include_tests": form.get("include_tests", "true") == "true",
            "dependencies": form.get("dependencies", ""),
            "env_vars": form.get("env_vars", ""),
            "services": {
                "postgres": form.get("svc_postgres", "false") == "true",
                "redis": form.get("svc_redis", "false") == "true",
            },
        }

    project_name = (data.get("project_name") or "my-project").strip()
    slug = slugify(project_name)

    context = {
        "project_name": project_name,
        "slug": slug,
        "description": (data.get("description") or "").strip(),
        "author": (data.get("author") or "").strip(),
        "license": (data.get("license") or "MIT").strip() or "MIT",
        "package_name": slugify(data.get("package_name") or project_name, separator="_"),
        "python_version": (data.get("python_version") or "3.11").strip(),
        "ci_provider": (data.get("ci_provider") or "github").strip(),
        "include_docker": bool(data.get("include_docker", True)),
        "include_tests": bool(data.get("include_tests", True)),
        "dependencies": data.get("dependencies") or "",
        "env_vars": data.get("env_vars") or "",
        "services": data.get("services") or {"postgres": False, "redis": False},
    }

    zip_bytes = generate_project_zip(context)
    zip_bytes.seek(0)

    return send_file(
        zip_bytes,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{slug}.zip",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/api/convert', methods=['POST'])
def _auto_stub_api_convert():
    return 'Auto-generated stub for /api/convert', 200
