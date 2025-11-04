import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import uuid
import hashlib
import datetime
import tempfile
import shutil
from flask import Flask, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from config import Config
from services.virus_scanner import VirusScanner
from utils.mime_utils import sniff_mime, extension_for_mime

config = Config()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

# Ensure directories exist with secure permissions
os.makedirs(config.STORAGE_ROOT, exist_ok=True)
os.makedirs(config.TMP_DIR, exist_ok=True)

# Apply a safer umask for created files/directories
try:
    os.umask(0o027)
except Exception:
    pass

scanner = VirusScanner(
    mode=config.CLAMAV_MODE,
    clamd_unix_socket=config.CLAMD_UNIX_SOCKET,
    clamd_host=config.CLAMD_HOST,
    clamd_port=config.CLAMD_PORT,
    clamscan_path=config.CLAMSCAN_PATH,
)


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(e):
    return jsonify({
        "error": "request_too_large",
        "message": f"Request exceeds maximum allowed size of {config.MAX_CONTENT_LENGTH} bytes"
    }), 413


@app.errorhandler(400)
def handle_bad_request(e):
    return jsonify({"error": "bad_request", "message": str(e)}), 400


@app.errorhandler(Exception)
def handle_generic_error(e):
    # Avoid leaking internal details
    return jsonify({"error": "internal_error", "message": "An internal error occurred."}), 500


@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "scanner_mode": scanner.mode}), 200


@app.post("/upload")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "no_file", "message": "No file part in the request"}), 400

    file_storage = request.files["file"]
    if not file_storage or file_storage.filename == "":
        return jsonify({"error": "no_filename", "message": "No selected file"}), 400

    original_name = secure_filename(file_storage.filename)

    # Stream to a secure temp file to avoid keeping the entire file in memory
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="up_", dir=config.TMP_DIR)
    os.close(tmp_fd)  # We'll reopen with normal file API

    hasher = hashlib.sha256()
    total = 0
    try:
        with open(tmp_path, "wb") as out:
            stream = file_storage.stream
            while True:
                chunk = stream.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total += len(chunk)
                if total > config.MAX_FILE_SIZE:
                    try:
                        out.flush()
                        os.fsync(out.fileno())
                    except Exception:
                        pass
                    out.close()
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    return jsonify({
                        "error": "file_too_large",
                        "message": f"File exceeds per-file limit of {config.MAX_FILE_SIZE} bytes"
                    }), 413
                hasher.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())

        detected_mime = sniff_mime(tmp_path)
        if detected_mime not in config.ALLOWED_MIME_TYPES:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({
                "error": "unsupported_type",
                "message": f"MIME type {detected_mime} is not allowed"
            }), 400

        scan_result = scanner.scan_file(tmp_path, timeout=config.CLAMAV_SCAN_TIMEOUT)
        if scan_result["status"] == "infected":
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({
                "error": "virus_detected",
                "message": f"Upload blocked: {scan_result.get('signature', 'malware')}"
            }), 400
        elif scan_result["status"] == "error":
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return jsonify({
                "error": "scan_error",
                "message": "Unable to complete virus scan"
            }), 500

        # Build a safe storage path: YYYY/MM/DD directories, randomized filename
        today = datetime.datetime.utcnow()
        subdir = os.path.join(str(today.year), f"{today.month:02d}", f"{today.day:02d}")
        target_dir = os.path.join(config.STORAGE_ROOT, subdir)
        os.makedirs(target_dir, mode=0o750, exist_ok=True)

        ext = extension_for_mime(detected_mime)
        file_id = uuid.uuid4().hex
        stored_name = f"{file_id}{ext}"
        final_path = os.path.join(target_dir, stored_name)

        # Move atomically
        os.replace(tmp_path, final_path)
        try:
            os.chmod(final_path, 0o640)
        except Exception:
            pass

        rel_path = os.path.relpath(final_path, config.STORAGE_ROOT)
        return jsonify({
            "message": "uploaded",
            "file": {
                "id": file_id,
                "original_name": original_name,
                "stored_name": stored_name,
                "size": total,
                "sha256": hasher.hexdigest(),
                "mime_type": detected_mime,
                "relative_path": rel_path
            }
        }), 201

    finally:
        # Cleanup temp if still present
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



def create_app():
    return app
