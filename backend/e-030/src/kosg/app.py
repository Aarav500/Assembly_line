from __future__ import annotations
import argparse
import json
import os
from flask import Flask, jsonify, request, make_response
from .generator import ScaffoldGenerator


def create_app() -> Flask:
    app = Flask(__name__)
    gen = ScaffoldGenerator()

    @app.get("/")
    def index():
        return jsonify({
            "name": "kubernetes-operator-scaffolding-generator-for-app-specific-o",
            "version": "0.1.0",
            "endpoints": ["GET /", "GET /healthz", "POST /generate?format=json|zip"],
        })

    @app.get("/healthz")
    def healthz():
        return ("ok", 200)

    @app.post("/generate")
    def generate():
        try:
            payload = request.get_json(force=True, silent=False) or {}
        except Exception as e:
            return jsonify({"error": f"Invalid JSON: {e}"}), 400
        out_format = request.args.get("format") or request.headers.get("Accept", "json")
        out_format = "zip" if "zip" in out_format else "json"
        if out_format == "zip":
            data = gen.as_zip_bytes(payload)
            resp = make_response(data)
            resp.headers["Content-Type"] = "application/zip"
            resp.headers["Content-Disposition"] = "attachment; filename=scaffold.zip"
            return resp
        else:
            files = gen.as_file_map(payload)
            return jsonify({"context": json.loads(json.dumps(payload)), "files": [{"path": k, "content": v} for k, v in files.items()]})

    return app


def serve_cli():
    parser = argparse.ArgumentParser(description="Serve the K8s operator scaffold generator API (Flask)")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port)


def generate_cli():
    parser = argparse.ArgumentParser(description="Generate a scaffold via CLI")
    parser.add_argument("--config", help="Path to JSON payload file (default: stdin)", default=None)
    parser.add_argument("--format", choices=["json", "zip"], default="json")
    parser.add_argument("--out-file", help="Output file (for zip) or JSON file (for json). If omitted, prints to stdout", default=None)
    parser.add_argument("--out-dir", help="Write files to a directory instead of zip/json output", default=None)
    args = parser.parse_args()

    import sys
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = json.load(sys.stdin)

    gen = ScaffoldGenerator()

    if args.out_dir:
        file_map = gen.as_file_map(payload)
        from pathlib import Path
        base = Path(args.out_dir)
        for path, content in file_map.items():
            out_path = base / path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
        print(f"Wrote {len(file_map)} files to {base}")
        return

    if args.format == "zip":
        data = gen.as_zip_bytes(payload)
        if args.out_file:
            with open(args.out_file, "wb") as f:
                f.write(data)
        else:
            sys.stdout.buffer.write(data)
    else:
        file_map = gen.as_file_map(payload)
        obj = {"files": [{"path": k, "content": v} for k, v in file_map.items()]}
        data = json.dumps(obj, indent=2)
        if args.out_file:
            with open(args.out_file, "w", encoding="utf-8") as f:
                f.write(data)
        else:
            print(data)

