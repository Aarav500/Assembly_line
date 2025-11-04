import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

import requests
from flask import Flask, jsonify, request, send_file

from generator import SDKGenerator, GenerationError

app = Flask(__name__)

def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status

@app.route("/health", methods=["GET"])  # Simple healthcheck
def health():
    return jsonify({"status": "ok"})

@app.route("/generate", methods=["POST"])  # Generate SDKs ZIP
def generate():
    if not request.is_json:
        return _error("Content-Type must be application/json")

    payload = request.get_json(silent=True) or {}

    # Input handling: spec can be provided as JSON object/string or URL to spec
    spec_dict: Optional[Dict[str, Any]] = None
    spec_text: Optional[str] = None
    spec_url: Optional[str] = None

    if "spec" in payload:
        if isinstance(payload["spec"], dict):
            spec_dict = payload["spec"]
        elif isinstance(payload["spec"], str):
            spec_text = payload["spec"]
        else:
            return _error("'spec' must be a JSON object or a YAML/JSON string")
    elif "url" in payload:
        spec_url = payload["url"]
        if not isinstance(spec_url, str) or not spec_url.strip():
            return _error("'url' must be a non-empty string")
    else:
        return _error("Provide either 'spec' (JSON/YAML string or object) or 'url'")

    languages: List[str] = payload.get("languages") or ["python", "typescript", "go", "java"]
    if not isinstance(languages, list) or not all(isinstance(l, str) for l in languages):
        return _error("'languages' must be a list of strings")

    overrides: Dict[str, Dict[str, Any]] = payload.get("overrides") or {}
    if not isinstance(overrides, dict):
        return _error("'overrides' must be an object keyed by language -> object")

    ts_opts: Dict[str, Any] = payload.get("typescript") or {}
    if not isinstance(ts_opts, dict):
        return _error("'typescript' options must be an object")

    custom_version: Optional[str] = payload.get("openapiGeneratorVersion")

    # Prepare temp workspace
    tmpdir = tempfile.mkdtemp(prefix="sdkgen_")
    try:
        # Write spec to temp file
        spec_path = os.path.join(tmpdir, "openapi-spec")
        spec_ext = "json"
        content_bytes: Optional[bytes] = None

        if spec_dict is not None:
            content_bytes = json.dumps(spec_dict, indent=2).encode("utf-8")
            spec_ext = "json"
        elif spec_text is not None:
            st = spec_text.lstrip()
            spec_ext = "json" if st.startswith("{") else "yaml"
            content_bytes = spec_text.encode("utf-8")
        elif spec_url:
            try:
                resp = requests.get(spec_url, timeout=60)
                resp.raise_for_status()
            except Exception as e:
                return _error(f"Failed to download spec from URL: {e}", 502)
            ct = resp.headers.get("Content-Type", "").lower()
            if "json" in ct:
                spec_ext = "json"
            elif "yaml" in ct or "yml" in ct:
                spec_ext = "yaml"
            else:
                # Try to infer from text content
                body = resp.text.lstrip()
                spec_ext = "json" if body.startswith("{") else "yaml"
                content_bytes = body.encode("utf-8")
            if content_bytes is None:
                content_bytes = resp.content
        else:
            return _error("No spec provided", 400)

        spec_path = f"{spec_path}.{spec_ext}"
        with open(spec_path, "wb") as f:
            f.write(content_bytes or b"")

        # Ensure generator JAR exists
        generator = SDKGenerator(version=custom_version)
        try:
            generator.ensure_cli()
        except GenerationError as ge:
            return _error(str(ge), 500)

        # Normalized languages and language-specific configs
        normalized_langs: List[str] = []
        supported = {"python", "typescript", "go", "java"}
        for lang in languages:
            l = lang.strip().lower()
            if l not in supported:
                return _error(f"Unsupported language: {lang}")
            if l not in normalized_langs:
                normalized_langs.append(l)

        out_root = os.path.join(tmpdir, "sdks")
        os.makedirs(out_root, exist_ok=True)

        results: Dict[str, Dict[str, Any]] = {}
        for lang in normalized_langs:
            out_dir = os.path.join(out_root, lang)
            os.makedirs(out_dir, exist_ok=True)

            additional: Dict[str, Any] = {}
            # apply overrides
            if lang in overrides and isinstance(overrides[lang], dict):
                additional.update(overrides[lang])

            # TS flavor (fetch/axios)
            ts_flavor = None
            if lang == "typescript":
                tf = ts_opts.get("flavor") if ts_opts else None
                if isinstance(tf, str):
                    ts_flavor = tf.strip().lower()
                # default to fetch
                if ts_flavor not in {"fetch", "axios"}:
                    ts_flavor = "fetch"

            try:
                gen_info = generator.generate_language(
                    language=lang,
                    spec_path=spec_path,
                    output_dir=out_dir,
                    additional_properties=additional,
                    ts_flavor=ts_flavor,
                )
                results[lang] = gen_info
            except GenerationError as ge:
                return _error(f"Failed generating {lang}: {ge}", 500)

        # Zip the outputs
        zip_path = os.path.join(tmpdir, "sdks.zip")
        import zipfile
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(out_root):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, out_root)
                    zf.write(full_path, arcname=rel_path)

        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name="sdks.zip",
        )

    finally:
        # cleanup temp directory after response is closed
        # Note: Werkzeug will close the file after sending; using call_on_close for robust cleanup would be ideal.
        @app.after_request
        def _cleanup(response):
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
            return response


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/api/users', methods=['GET', 'POST'])
def _auto_stub_api_users():
    return 'Auto-generated stub for /api/users', 200


@app.route('/api/users/1', methods=['GET'])
def _auto_stub_api_users_1():
    return 'Auto-generated stub for /api/users/1', 200


@app.route('/api/users/999', methods=['GET'])
def _auto_stub_api_users_999():
    return 'Auto-generated stub for /api/users/999', 200
