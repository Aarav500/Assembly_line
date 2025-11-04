import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
import datetime as dt
from flask import Flask, jsonify, request, send_file, render_template
from sbom.scanner import scan_environment, scan_requirements, scan_pyproject
from sbom.sbom import build_spdx_like_sbom, summarize_licenses

app = Flask(__name__)


def _iso_now():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/sbom")
def api_sbom():
    try:
        source = request.args.get("source", "installed").lower()
        path = request.args.get("path")
        project_name = request.args.get("project")

        if source == "installed":
            packages = scan_environment()
        elif source == "requirements":
            if not path:
                return jsonify({"error": "Missing 'path' query param to requirements.txt"}), 400
            packages = scan_requirements(path)
        elif source == "pyproject":
            if not path:
                return jsonify({"error": "Missing 'path' query param to pyproject.toml"}), 400
            packages = scan_pyproject(path)
        else:
            return jsonify({"error": "Unknown source. Use one of: installed, requirements, pyproject"}), 400

        sbom = build_spdx_like_sbom(packages, project_name=project_name)
        return jsonify(sbom)
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permission denied: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.get("/api/licenses")
def api_licenses():
    try:
        source = request.args.get("source", "installed").lower()
        path = request.args.get("path")

        if source == "installed":
            packages = scan_environment()
        elif source == "requirements":
            if not path:
                return jsonify({"error": "Missing 'path' query param to requirements.txt"}), 400
            packages = scan_requirements(path)
        elif source == "pyproject":
            if not path:
                return jsonify({"error": "Missing 'path' query param to pyproject.toml"}), 400
            packages = scan_pyproject(path)
        else:
            return jsonify({"error": "Unknown source. Use one of: installed, requirements, pyproject"}), 400

        summary = summarize_licenses(packages)
        return jsonify({
            "generated": _iso_now(),
            "totalPackages": len(packages),
            "licenses": summary,
        })
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permission denied: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.get("/api/packages")
def api_packages():
    try:
        source = request.args.get("source", "installed").lower()
        path = request.args.get("path")

        if source == "installed":
            packages = scan_environment()
        elif source == "requirements":
            if not path:
                return jsonify({"error": "Missing 'path' query param to requirements.txt"}), 400
            packages = scan_requirements(path)
        elif source == "pyproject":
            if not path:
                return jsonify({"error": "Missing 'path' query param to pyproject.toml"}), 400
            packages = scan_pyproject(path)
        else:
            return jsonify({"error": "Unknown source. Use one of: installed, requirements, pyproject"}), 400

        return jsonify(packages)
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permission denied: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.get("/download/sbom.json")
def download_sbom():
    try:
        source = request.args.get("source", "installed").lower()
        path = request.args.get("path")
        project_name = request.args.get("project")

        if source == "installed":
            packages = scan_environment()
        elif source == "requirements":
            if not path:
                return jsonify({"error": "Missing 'path' query param to requirements.txt"}), 400
            packages = scan_requirements(path)
        elif source == "pyproject":
            if not path:
                return jsonify({"error": "Missing 'path' query param to pyproject.toml"}), 400
            packages = scan_pyproject(path)
        else:
            return jsonify({"error": "Unknown source. Use one of: installed, requirements, pyproject"}), 400

        sbom = build_spdx_like_sbom(packages, project_name=project_name)
        
        buffer = io.BytesIO()
        buffer.write(json.dumps(sbom, indent=2).encode('utf-8'))
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/json',
            as_attachment=True,
            download_name='sbom.json'
        )
    except FileNotFoundError as e:
        return jsonify({"error": f"File not found: {str(e)}"}), 404
    except PermissionError as e:
        return jsonify({"error": f"Permission denied: {str(e)}"}), 403
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.route('/ready')
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}


if __name__ == '__main__':
    pass
