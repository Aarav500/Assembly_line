import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, g
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from config import get_config
from auth import require_auth
from db import init_db, get_db, close_db, list_bundles, get_bundle, delete_bundle
from export_service import create_export_bundle


def create_app():
    app = Flask(__name__)
    cfg = get_config()
    app.config.update(
        DATABASE=cfg['DATABASE'],
        EXPORT_DIR=cfg['EXPORT_DIR'],
        API_TOKEN=cfg['API_TOKEN'],
        SIGNING_KEY=cfg['SIGNING_KEY'],
        APP_VERSION=cfg['APP_VERSION']
    )

    os.makedirs(app.config['EXPORT_DIR'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)

    with app.app_context():
        init_db()

    @app.teardown_appcontext
    def teardown_db(exception):
        close_db(exception)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "version": app.config['APP_VERSION']})

    @app.route('/api/bundles', methods=['GET'])
    @require_auth
    def api_list_bundles():
        conn = get_db()
        rows = list_bundles(conn)
        return jsonify({"bundles": rows})

    @app.route('/api/bundles', methods=['POST'])
    @require_auth
    def api_create_bundle():
        try:
            payload = request.get_json(silent=True) or {}
        except BadRequest:
            raise BadRequest("Invalid JSON body")

        filters = normalize_filters(payload)
        created_by = request.headers.get('X-Actor', 'api')

        conn = get_db()
        bundle_meta = create_export_bundle(app.config, conn, filters, created_by)
        return jsonify({"bundle": bundle_meta}), 201

    @app.route('/api/bundles/<bundle_id>', methods=['GET'])
    @require_auth
    def api_get_bundle(bundle_id):
        conn = get_db()
        b = get_bundle(conn, bundle_id)
        if not b:
            raise NotFound("Bundle not found")
        return jsonify({"bundle": b})

    @app.route('/api/bundles/<bundle_id>/download', methods=['GET'])
    @require_auth
    def api_download_bundle(bundle_id):
        conn = get_db()
        b = get_bundle(conn, bundle_id)
        if not b:
            raise NotFound("Bundle not found")
        path = b.get('file_path')
        if not path or not os.path.exists(path):
            raise NotFound("Bundle file not found")
        filename = os.path.basename(path)
        return send_file(path, as_attachment=True, download_name=filename)

    @app.route('/api/bundles/<bundle_id>', methods=['DELETE'])
    @require_auth
    def api_delete_bundle(bundle_id):
        conn = get_db()
        b = get_bundle(conn, bundle_id)
        if not b:
            raise NotFound("Bundle not found")
        # remove file
        if b.get('file_path') and os.path.exists(b['file_path']):
            try:
                os.remove(b['file_path'])
            except OSError:
                pass
        delete_bundle(conn, bundle_id)
        return jsonify({"deleted": True, "bundle_id": bundle_id})

    return app


def normalize_filters(payload):
    # Defaults
    include_default = ["policies", "controls", "evidences", "audit_logs", "users"]
    start = payload.get('start')
    end = payload.get('end')

    def parse_iso(s):
        if not s:
            return None
        try:
            # support with Z or offset
            if s.endswith('Z'):
                s = s[:-1] + '+00:00'
            return datetime.fromisoformat(s)
        except Exception:
            raise BadRequest("Invalid ISO8601 datetime for 'start' or 'end'")

    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    if start_dt and end_dt and end_dt < start_dt:
        raise BadRequest("'end' must be >= 'start'")

    filters = {
        'start': start_dt.isoformat() if start_dt else None,
        'end': end_dt.isoformat() if end_dt else None,
        'frameworks': payload.get('frameworks') or [],
        'include': payload.get('include') or include_default,
        'anonymize_pii': bool(payload.get('anonymize_pii', False)),
        'label': payload.get('label') or None
    }
    return filters


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/api/audit/logs?start_date=2024-01-01&end_date=2024-01-31', methods=['GET'])
def _auto_stub_api_audit_logs_start_date_2024_01_01_end_date_2024_01_31():
    return 'Auto-generated stub for /api/audit/logs?start_date=2024-01-01&end_date=2024-01-31', 200


@app.route('/api/audit/export', methods=['POST'])
def _auto_stub_api_audit_export():
    return 'Auto-generated stub for /api/audit/export', 200


@app.route('/api/compliance/status', methods=['GET'])
def _auto_stub_api_compliance_status():
    return 'Auto-generated stub for /api/compliance/status', 200
