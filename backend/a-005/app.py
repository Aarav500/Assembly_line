import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
import shutil
import tempfile
from flask import Flask, request, jsonify
from fingerprint.analyzer import analyze_directory
from fingerprint.utils import safe_extract_zip

app = Flask(__name__)

IGNORED_UPLOAD_SIZE = 200 * 1024 * 1024  # 200MB safety limit

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/fingerprint", methods=["POST"])
def fingerprint_upload():
    if 'file' not in request.files:
        return jsonify({"error": "file is required (zip archive)"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "empty filename"}), 400

    # Simple size guard (Content-Length may not be present)
    # Buffer to a temporary file while checking size
    tmp_fd, tmp_zip_path = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_fd)
    total = 0

    try:
        with open(tmp_zip_path, 'wb') as out:
            chunk = file.stream.read(8192)
            while chunk:
                total += len(chunk)
                if total > IGNORED_UPLOAD_SIZE:
                    return jsonify({"error": "upload too large"}), 413
                out.write(chunk)
                chunk = file.stream.read(8192)

        temp_dir = tempfile.mkdtemp(prefix="pfp_")
        try:
            safe_extract_zip(tmp_zip_path, temp_dir)
            # If the zip has a single top-level folder, use it as root
            entries = [e for e in os.listdir(temp_dir) if not e.startswith('.')] 
            root_dir = temp_dir
            if len(entries) == 1 and os.path.isdir(os.path.join(temp_dir, entries[0])):
                root_dir = os.path.join(temp_dir, entries[0])

            result = analyze_directory(root_dir)
            return jsonify(result)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    finally:
        try:
            os.remove(tmp_zip_path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))



def create_app():
    return app
