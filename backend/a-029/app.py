import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
from datetime import datetime
from flask import Flask, request, jsonify, make_response

from reporting.md_builder import build_markdown_report
from reporting.pdf_builder import build_pdf_report
from reporting.utils import slugify, with_defaults

app = Flask(__name__)


@app.route("/reports/export", methods=["POST"]) 
def export_report():
    fmt = (request.args.get("format") or request.args.get("fmt") or "pdf").lower()
    payload = request.get_json(silent=True) or {}

    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid JSON payload"}), 400

    data = with_defaults(payload)

    filename_base = slugify(data.get("project", {}).get("name") or "project-report")
    generated_at_iso = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename_base = f"{filename_base}-{generated_at_iso}"

    if fmt in ("md", "markdown"):
        md = build_markdown_report(data)
        resp = make_response(md)
        resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
        resp.headers["Content-Disposition"] = f"attachment; filename={filename_base}.md"
        return resp
    elif fmt == "pdf":
        pdf_bytes = build_pdf_report(data)
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f"attachment; filename={filename_base}.pdf"
        return resp
    else:
        return jsonify({"error": "Unsupported format. Use 'pdf' or 'md'."}), 400


@app.route("/reports/sample", methods=["GET"]) 
def sample_payload():
    import json
    sample_path = os.path.join(os.path.dirname(__file__), "sample_payload.json")
    with open(sample_path, "r", encoding="utf-8") as f:
        return make_response(f.read(), 200, {"Content-Type": "application/json; charset=utf-8"})


@app.route("/reports/demo", methods=["GET"]) 
def demo_report():
    import json
    fmt = (request.args.get("format") or request.args.get("fmt") or "pdf").lower()
    sample_path = os.path.join(os.path.dirname(__file__), "sample_payload.json")
    with open(sample_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data = with_defaults(data)

    filename_base = slugify(data.get("project", {}).get("name") or "project-report-demo")

    if fmt in ("md", "markdown"):
        md = build_markdown_report(data)
        resp = make_response(md)
        resp.headers["Content-Type"] = "text/markdown; charset=utf-8"
        resp.headers["Content-Disposition"] = f"attachment; filename={filename_base}-demo.md"
        return resp
    elif fmt == "pdf":
        pdf_bytes = build_pdf_report(data)
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = f"attachment; filename={filename_base}-demo.pdf"
        return resp
    else:
        return jsonify({"error": "Unsupported format. Use 'pdf' or 'md'."}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app
