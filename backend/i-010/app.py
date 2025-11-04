import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, Response
from config import Config
from database import db, init_db
from services.scan_manager import ScanManager
from services.scanners.dummy_scanner import DummyScanner
try:
    from services.scanners.zap_client import ZapScanner
except Exception:
    ZapScanner = None
from models import Scan, Report
from utils.security import require_api_key


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    init_db(app)

    scanners = {"dummy": DummyScanner()}
    if app.config.get("ZAP_API_URL") and ZapScanner:
        scanners["zap"] = ZapScanner(
            api_url=app.config.get("ZAP_API_URL"),
            api_key=app.config.get("ZAP_API_KEY"),
            context_name=app.config.get("ZAP_CONTEXT_NAME"),
            poll_interval=app.config.get("SCAN_POLL_INTERVAL", 5),
            max_duration=app.config.get("SCAN_MAX_DURATION", 900),
        )

    app.extensions["scan_manager"] = ScanManager(
        app=app,
        db=db,
        scanners=scanners,
        allowed_targets=app.config.get("ALLOWED_TARGETS", []),
        report_storage_path=app.config.get("REPORT_STORAGE_PATH"),
    )

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/api/scans")
    @require_api_key
    def create_scan():
        data = request.get_json(force=True, silent=True) or {}
        target_url = data.get("target_url")
        scanner = data.get("scanner", "dummy")
        metadata = data.get("metadata") or {}
        if not target_url:
            return jsonify({"error": "target_url is required"}), 400
        manager: ScanManager = app.extensions["scan_manager"]
        try:
            scan = manager.start_scan(target_url=target_url, scanner_name=scanner, metadata=metadata)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(scan.to_dict()), 202

    @app.get("/api/scans")
    @require_api_key
    def list_scans():
        q = Scan.query.order_by(Scan.created_at.desc())
        scanner = request.args.get("scanner")
        status = request.args.get("status")
        target = request.args.get("target")
        if scanner:
            q = q.filter_by(scanner=scanner)
        if status:
            q = q.filter_by(status=status)
        if target:
            q = q.filter(Scan.target_url.like(f"%{target}%"))
        items = [s.to_dict() for s in q.limit(200).all()]
        return jsonify({"items": items})

    @app.get("/api/scans/<string:scan_id>")
    @require_api_key
    def get_scan(scan_id: str):
        scan = Scan.query.get(scan_id)
        if not scan:
            return jsonify({"error": "not_found"}), 404
        return jsonify(scan.to_dict(include_report_summary=True))

    @app.get("/api/scans/<string:scan_id>/report")
    @require_api_key
    def get_report(scan_id: str):
        scan = Scan.query.get(scan_id)
        if not scan:
            return jsonify({"error": "not_found"}), 404
        if not scan.report_id:
            return jsonify({"error": "report_not_available"}), 404
        report = Report.query.get(scan.report_id)
        fmt = request.args.get("format", "json").lower()
        if fmt == "json":
            return jsonify(report.to_dict())
        elif fmt == "html":
            return Response(report.html or "<html><body><p>No HTML report available.</p></body></html>", mimetype="text/html")
        else:
            return jsonify({"error": "unsupported_format"}), 400

    @app.post("/api/webhooks/trigger")
    def webhook_trigger():
        secret = app.config.get("WEBHOOK_SECRET")
        if secret:
            signature = request.headers.get("X-Hub-Signature-256") or request.headers.get("X-Signature")
            body = request.get_data() or b""
            from utils.security import verify_hmac_signature
            if not verify_hmac_signature(secret.encode(), body, signature):
                return jsonify({"error": "invalid_signature"}), 403
        payload = request.get_json(force=True, silent=True) or {}
        event_type = request.headers.get("X-Event-Type") or payload.get("event_type") or "generic"
        target_url = payload.get("target_url")
        scanner = payload.get("scanner") or "dummy"
        metadata = payload.get("metadata") or {"source": "webhook", "event_type": event_type}
        if not target_url:
            return jsonify({"error": "target_url is required"}), 400
        manager: ScanManager = app.extensions["scan_manager"]
        try:
            scan = manager.start_scan(target_url=target_url, scanner_name=scanner, metadata=metadata)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"accepted": True, "scan": scan.to_dict()})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



@app.route('/trigger-test', methods=['POST'])
def _auto_stub_trigger_test():
    return 'Auto-generated stub for /trigger-test', 200


@app.route('/reports', methods=['GET'])
def _auto_stub_reports():
    return 'Auto-generated stub for /reports', 200
