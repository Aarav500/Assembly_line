import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

from config import Config
from storage import S3Storage, LocalStorage, safe_filename

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config())

    # Signer for local signed URLs
    app.signer = URLSafeTimedSerializer(app.config["APP_SECRET_KEY"], salt="local-storage")

    # Storage backend
    if app.config["STORAGE_BACKEND"].lower() == "s3":
        app.storage = S3Storage(
            bucket=app.config["S3_BUCKET"],
            region=app.config["S3_REGION"],
            upload_expires=app.config["S3_UPLOAD_EXPIRATION"],
            download_expires=app.config["S3_DOWNLOAD_EXPIRATION"],
            max_file_size=app.config["MAX_FILE_SIZE_BYTES"],
            allowed_mime_prefixes=app.config["ALLOWED_MIME_PREFIXES"],
            acl=app.config["S3_DEFAULT_ACL"],
        )
    else:
        app.storage = LocalStorage(
            base_dir=app.config["LOCAL_STORAGE_PATH"],
            signer=app.signer,
            upload_expires=app.config["LOCAL_UPLOAD_EXPIRATION"],
            download_expires=app.config["LOCAL_DOWNLOAD_EXPIRATION"],
            max_file_size=app.config["MAX_FILE_SIZE_BYTES"],
            allowed_mime_prefixes=app.config["ALLOWED_MIME_PREFIXES"],
        )

    @app.errorhandler(Exception)
    def handle_error(e):
        if isinstance(e, HTTPException):
            return jsonify(error=e.name, message=e.description), e.code
        return jsonify(error="InternalServerError", message=str(e)), 500

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify(status="ok", time=datetime.utcnow().isoformat() + "Z")

    @app.route("/api/files/presign-upload", methods=["POST"])
    def presign_upload():
        data = request.get_json(silent=True) or {}
        filename = data.get("filename")
        content_type = data.get("content_type")
        content_length = data.get("content_length")
        metadata = data.get("metadata") or {}
        prefix = data.get("prefix") or "uploads/"

        if not filename or not content_type or not content_length:
            return jsonify(error="BadRequest", message="filename, content_type, content_length are required"), 400

        try:
            content_length = int(content_length)
        except Exception:
            return jsonify(error="BadRequest", message="content_length must be an integer"), 400

        if content_length <= 0:
            return jsonify(error="BadRequest", message="content_length must be positive"), 400

        if content_length > app.config["MAX_FILE_SIZE_BYTES"]:
            return jsonify(error="BadRequest", message=f"File exceeds max size {app.config['MAX_FILE_SIZE_BYTES']} bytes"), 400

        # Build key
        key = app.storage.create_key(filename=filename, prefix=prefix)

        # Create upload URL
        upload_info = app.storage.create_upload_url(
            key=key,
            content_type=content_type,
            content_length=content_length,
            metadata=metadata,
        )

        return jsonify(
            upload=upload_info,
            file={
                "key": key,
                "bucket": getattr(app.storage, "bucket", None),
                "content_type": content_type,
                "content_length": content_length,
            },
        )

    @app.route("/api/files/presign-download", methods=["GET"])
    def presign_download():
        key = request.args.get("key")
        if not key:
            return jsonify(error="BadRequest", message="key is required"), 400

        as_attachment = request.args.get("as_attachment", "false").lower() == "true"
        filename = request.args.get("filename")
        response_content_type = request.args.get("content_type")

        disposition = None
        if as_attachment:
            name = filename or Path(key).name
            disposition = f"attachment; filename=\"{safe_filename(name)}\""

        url, expires_in = app.storage.create_download_url(
            key=key,
            response_content_type=response_content_type,
            response_content_disposition=disposition,
        )

        return jsonify(url=url, expires_in=expires_in, key=key)

    # Local-only upload endpoint (signed)
    @app.route("/_local/upload", methods=["PUT"])
    def local_upload():
        if not isinstance(app.storage, LocalStorage):
            return jsonify(error="NotFound", message="Route not available for current storage backend"), 404

        token = request.args.get("token")
        if not token:
            return jsonify(error="Unauthorized", message="Missing token"), 401

        try:
            payload = app.storage.verify_token(token, scope="upload")
        except SignatureExpired:
            return jsonify(error="Unauthorized", message="Token expired"), 401
        except BadSignature:
            return jsonify(error="Unauthorized", message="Invalid token"), 401

        key = payload["key"]
        expected_ct = payload["content_type"]
        max_len = min(payload["content_length"], app.config["MAX_FILE_SIZE_BYTES"])

        req_ct = request.headers.get("Content-Type")
        if req_ct != expected_ct:
            return jsonify(error="BadRequest", message="Content-Type mismatch"), 400

        try:
            content_length = int(request.headers.get("Content-Length", "0"))
        except Exception:
            return jsonify(error="BadRequest", message="Invalid Content-Length"), 400

        if content_length <= 0 or content_length > max_len:
            return jsonify(error="BadRequest", message="Invalid or too large Content-Length"), 400

        file_path = app.storage.path_for_key(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        bytes_written = 0
        with open(file_path, "wb") as f:
            # Stream copy
            chunk = request.stream.read(64 * 1024)
            while chunk:
                f.write(chunk)
                bytes_written += len(chunk)
                if bytes_written > max_len:
                    f.close()
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return jsonify(error="BadRequest", message="Uploaded data exceeds allowed size"), 400
                chunk = request.stream.read(64 * 1024)

        if bytes_written != content_length:
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
            return jsonify(error="BadRequest", message="Size mismatch"), 400

        return jsonify(status="uploaded", key=key, size=bytes_written)

    # Local-only download endpoint (signed)
    @app.route("/_local/download/<path:key>", methods=["GET"])
    def local_download(key: str):
        if not isinstance(app.storage, LocalStorage):
            return jsonify(error="NotFound", message="Route not available for current storage backend"), 404

        token = request.args.get("token")
        if not token:
            return jsonify(error="Unauthorized", message="Missing token"), 401

        try:
            payload = app.storage.verify_token(token, scope="download")
        except SignatureExpired:
            return jsonify(error="Unauthorized", message="Token expired"), 401
        except BadSignature:
            return jsonify(error="Unauthorized", message="Invalid token"), 401

        if payload.get("key") != key:
            return jsonify(error="Unauthorized", message="Token key mismatch"), 401

        path = app.storage.path_for_key(key)
        if not path.exists():
            return jsonify(error="NotFound", message="File not found"), 404

        as_attachment = request.args.get("as_attachment", "false").lower() == "true"
        filename = request.args.get("filename") or Path(key).name
        return send_file(path, as_attachment=as_attachment, download_name=safe_filename(filename))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))



@app.route('/files/upload', methods=['POST'])
def _auto_stub_files_upload():
    return 'Auto-generated stub for /files/upload', 200
