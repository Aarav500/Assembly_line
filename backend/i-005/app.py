import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from pii_redactor.redactor import PiiRedactor
from pii_redactor.logging_filter import configure_logging
from storage import Storage


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure data directories exist
    os.makedirs(app.config['REDACTED_DIR'], exist_ok=True)
    os.makedirs(app.config['LOG_DIR'], exist_ok=True)

    # PII Redactor and Storage
    redactor = PiiRedactor()
    storage = Storage(redacted_dir=app.config['REDACTED_DIR'])

    # Configure logging with PII redaction
    logger = configure_logging(app_name='pii-redactor', log_dir=app.config['LOG_DIR'], level=app.config['LOG_LEVEL'], redactor=redactor)
    app.logger = logger

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_file(e):
        return jsonify({"error": "File too large", "max_bytes": app.config['MAX_CONTENT_LENGTH']}), 413

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + 'Z'})

    @app.route('/', methods=['GET'])
    def index():
        return jsonify({
            "service": "PII detection & redaction",
            "endpoints": [
                {"method": "POST", "path": "/upload", "desc": "Upload text to redact PII"},
                {"method": "GET", "path": "/files/<id>", "desc": "Retrieve redacted file and metadata"},
                {"method": "POST", "path": "/logs/test", "desc": "Emit a test log message with redaction"},
                {"method": "GET", "path": "/health", "desc": "Health check"}
            ]
        })

    def _read_text_from_request(req):
        # Prefer JSON body
        if req.is_json:
            payload = req.get_json(silent=True) or {}
            if isinstance(payload, dict) and 'content' in payload:
                return str(payload['content']), 'json'
        # Form field
        if 'content' in req.form:
            return str(req.form.get('content')), 'form'
        # File upload
        if 'file' in req.files:
            f = req.files['file']
            filename = secure_filename(f.filename or '')
            try:
                data = f.read()
                # Try utf-8 then latin-1 as fallback
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    text = data.decode('latin-1')
                return text, f"file:{filename}"
            except Exception:
                return None, None
        return None, None

    @app.route('/upload', methods=['POST'])
    def upload():
        text, source = _read_text_from_request(request)
        if text is None:
            return jsonify({"error": "No content provided. Use JSON {content}, form field 'content', or upload a text file as 'file'."}), 400

        # Redact PII
        result = redactor.redact(text)
        redacted_text = result['redacted_text']

        # Build metadata
        file_id = uuid.uuid4().hex
        sha256 = hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()
        metadata = {
            'id': file_id,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'source': source,
            'original': {
                'sha256': sha256,
                'length': len(text)
            },
            'pii': {
                'total_matches': result['total_matches'],
                'counts_by_type': result['counts_by_type'],
                'sample_matches': result['sample_matches']
            },
            'config': {
                'store_original': False
            }
        }

        # Persist redacted content and metadata
        storage.save(file_id=file_id, redacted_text=redacted_text, metadata=metadata)

        app.logger.info(
            "Redaction completed id=%s source=%s matches=%s counts=%s", 
            file_id,
            source,
            result['total_matches'],
            result['counts_by_type']
        )

        return jsonify({
            'id': file_id,
            'total_matches': result['total_matches'],
            'counts_by_type': result['counts_by_type'],
            'redacted_preview': redacted_text[:300],
            'links': {
                'get': f"/files/{file_id}"
            }
        })

    @app.route('/files/<file_id>', methods=['GET'])
    def get_file(file_id):
        # Return metadata and optionally content
        include_content = request.args.get('download') == '1' or request.args.get('include') == 'content'
        meta = storage.load_metadata(file_id)
        if not meta:
            abort(404)
        response = {'metadata': meta}
        if include_content:
            content = storage.load_redacted(file_id)
            if content is None:
                abort(404)
            response['redacted_text'] = content
        return jsonify(response)

    @app.route('/logs/test', methods=['POST'])
    def logs_test():
        payload = request.get_json(silent=True) or {}
        msg = str(payload.get('message', 'Example log with email john.doe@example.com and phone (555) 123-4567. CC 4111 1111 1111 1111'))
        app.logger.info("User provided message: %s", msg)
        # Also return redacted version to demonstrate
        redacted = redactor.redact_string(msg)
        return jsonify({
            'input': msg,
            'redacted': redacted
        })

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=bool(os.getenv('DEBUG', '0') == '1'))



@app.route('/redact', methods=['POST'])
def _auto_stub_redact():
    return 'Auto-generated stub for /redact', 200
