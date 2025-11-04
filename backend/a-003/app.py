import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
import base64
import tempfile
import zipfile
from flask import Flask, request, jsonify
from detector import detect_project_types

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def _extract_zip_to_temp(file_bytes: bytes) -> str:
    tmpdir = tempfile.mkdtemp(prefix="projdetect_")
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        # Prevent Zip Slip
        for member in zf.infolist():
            extracted_path = os.path.realpath(os.path.join(tmpdir, member.filename))
            if not extracted_path.startswith(os.path.realpath(tmpdir) + os.sep) and extracted_path != os.path.realpath(tmpdir):
                raise RuntimeError("Invalid zip entry path")
        zf.extractall(tmpdir)
    # If the zip contains a single top-level directory, use that as the root
    try:
        entries = [e for e in os.listdir(tmpdir) if not e.startswith("__MACOSX")]
        if len(entries) == 1:
            candidate = os.path.join(tmpdir, entries[0])
            if os.path.isdir(candidate):
                return candidate
    except Exception:
        pass
    return tmpdir


@app.post("/detect")
def detect():
    # Supports:
    # - JSON body: {"path": "/path/to/project"}
    # - JSON body: {"zip_base64": "..."}
    # - multipart/form-data with a file field named "file" (zip)
    scan_path = None
    cleanup_dir = None

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file provided"}), 400
        try:
            data = file.read()
            scan_path = _extract_zip_to_temp(data)
            cleanup_dir = os.path.dirname(scan_path) if os.path.basename(scan_path) else scan_path
        except Exception as e:
            return jsonify({"error": f"Failed to extract zip: {e}"}), 400
    else:
        try:
            payload = request.get_json(silent=True) or {}
        except Exception:
            payload = {}
        if "zip_base64" in (payload or {}):
            try:
                data = base64.b64decode(payload["zip_base64"])
                scan_path = _extract_zip_to_temp(data)
                cleanup_dir = os.path.dirname(scan_path) if os.path.basename(scan_path) else scan_path
            except Exception as e:
                return jsonify({"error": f"Failed to decode/extract zip_base64: {e}"}), 400
        else:
            scan_path = (payload or {}).get("path") or os.getcwd()
            if not os.path.exists(scan_path):
                return jsonify({"error": f"Path does not exist: {scan_path}"}), 400

    try:
        result = detect_project_types(scan_path)
        return jsonify(result)
    finally:
        # If needed, leave temp dir cleanup to the OS; no explicit deletion to allow post-inspection.
        # Alternatively, implement a background cleanup if desired.
        pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



def create_app():
    return app
