import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, abort
from werkzeug.utils import secure_filename

from config import Config
from models import db, Artifact, Bundle, ApprovalRequest, Approver, bundle_artifacts
from services.storage import ensure_storage, save_uploaded_file, create_bundle_zip, compute_checksum, fetch_url_to_artifact
from services.notifications import NotificationService


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Ensure storage directories
    ensure_storage(app.config['STORAGE_DIR'])

    db.init_app(app)

    with app.app_context():
        db.create_all()

    notifier = NotificationService(app.config)

    @app.get('/health')
    def health():
        return jsonify({"status": "ok"})

    @app.post('/api/artifacts')
    def upload_artifacts():
        if 'files' not in request.files:
            return jsonify({"error": "No files part in request. Use multipart/form-data with files[]"}), 400

        files = request.files.getlist('files')
        metadata = request.form.get('metadata')
        artifacts = []
        for f in files:
            if not f.filename:
                continue
            filename = secure_filename(f.filename)
            stored_path, size = save_uploaded_file(f, app.config['STORAGE_DIR'])
            checksum = compute_checksum(stored_path)
            artifact = Artifact(filename=filename, path=stored_path, size=size, checksum=checksum, metadata=metadata)
            db.session.add(artifact)
            artifacts.append(artifact)
        db.session.commit()
        return jsonify({"artifacts": [a.to_dict() for a in artifacts]})

    @app.post('/api/artifacts/fetch')
    def fetch_artifacts():
        data = request.get_json(silent=True) or {}
        urls = data.get('urls') or []
        if not urls:
            return jsonify({"error": "No urls provided"}), 400
        artifacts = []
        for url in urls:
            try:
                artifact = fetch_url_to_artifact(url, app.config['STORAGE_DIR'])
                db.session.add(artifact)
                artifacts.append(artifact)
            except Exception as e:
                return jsonify({"error": f"Failed to fetch {url}: {e}"}), 400
        db.session.commit()
        return jsonify({"artifacts": [a.to_dict() for a in artifacts]})

    @app.post('/api/bundle')
    def create_bundle():
        data = request.get_json(silent=True) or {}
        name = data.get('name') or f"bundle-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        artifact_ids = data.get('artifact_ids') or []
        if not artifact_ids:
            return jsonify({"error": "artifact_ids required"}), 400
        artifacts = Artifact.query.filter(Artifact.id.in_(artifact_ids)).all()
        if not artifacts:
            return jsonify({"error": "No valid artifacts found"}), 404
        bundle = Bundle(name=name)
        db.session.add(bundle)
        db.session.flush()
        for a in artifacts:
            db.session.execute(bundle_artifacts.insert().values(bundle_id=bundle.id, artifact_id=a.id))
        zip_path = create_bundle_zip(bundle, artifacts, app.config['STORAGE_DIR'])
        bundle.zip_path = zip_path
        db.session.commit()
        return jsonify({"bundle": bundle.to_dict(include_artifacts=True)})

    @app.get('/api/bundles/<int:bundle_id>/download')
    def download_bundle(bundle_id):
        bundle = Bundle.query.get_or_404(bundle_id)
        if not bundle.zip_path or not os.path.isfile(bundle.zip_path):
            return jsonify({"error": "Bundle not found on disk"}), 404
        return send_file(bundle.zip_path, as_attachment=True)

    @app.post('/api/requests')
    def create_request():
        data = request.get_json(silent=True) or {}
        bundle_id = data.get('bundle_id')
        title = data.get('title') or 'Audit Approval Request'
        description = data.get('description')
        due_at = data.get('due_at')
        notify = bool(data.get('notify', True))
        approvers = data.get('approvers') or []  # list of {email, name}
        if not bundle_id:
            return jsonify({"error": "bundle_id required"}), 400
        bundle = Bundle.query.get(bundle_id)
        if not bundle:
            return jsonify({"error": "Bundle not found"}), 404
        req = ApprovalRequest(bundle_id=bundle.id, title=title, description=description, status='PENDING')
        if due_at:
            try:
                req.due_at = datetime.fromisoformat(due_at)
            except Exception:
                return jsonify({"error": "Invalid due_at. Use ISO 8601."}), 400
        db.session.add(req)
        db.session.flush()
        created_approvers = []
        for ap in approvers:
            email = (ap.get('email') or '').strip()
            name = (ap.get('name') or '').strip() or email
            if not email:
                continue
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            approver = Approver(request_id=req.id, email=email, name=name, token_hash=token_hash, decision='PENDING')
            db.session.add(approver)
            db.session.flush()
            created_approvers.append((approver, token))
        db.session.commit()

        if notify and created_approvers:
            for approver, token in created_approvers:
                approve_url = url_for('approval_form', request_id=req.id, token=token, _external=True)
                bundle_url = url_for('download_bundle', bundle_id=bundle.id, _external=True)
                notifier.send_request_email(approver.email, approver.name, req, approve_url, bundle_url)
        return jsonify({"request": req.to_dict(include_approvers=True)})

    @app.get('/api/requests/<int:req_id>')
    def get_request(req_id):
        req = ApprovalRequest.query.get_or_404(req_id)
        return jsonify({"request": req.to_dict(include_approvers=True)})

    @app.post('/api/requests/<int:req_id>/approve')
    def approve_request(req_id):
        req = ApprovalRequest.query.get_or_404(req_id)
        data = request.get_json(silent=True) or {}
        token = data.get('token')
        decision = (data.get('decision') or '').upper()
        signature_text = data.get('signature_text')
        comment = data.get('comment')
        if not token:
            return jsonify({"error": "token required"}), 400
        if decision not in ('APPROVED', 'REJECTED'):
            return jsonify({"error": "decision must be APPROVED or REJECTED"}), 400
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        approver = Approver.query.filter_by(request_id=req.id, token_hash=token_hash).first()
        if not approver:
            return jsonify({"error": "Invalid token"}), 403
        if approver.decision in ('APPROVED', 'REJECTED'):
            return jsonify({"error": "Decision already recorded"}), 400
        approver.decision = decision
        approver.signature_text = signature_text
        approver.comment = comment
        approver.signer_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        approver.approved_at = datetime.utcnow()
        _update_request_status(req)
        db.session.commit()
        return jsonify({"request": req.to_dict(include_approvers=True)})

    def _update_request_status(req: ApprovalRequest):
        # If any rejected -> REJECTED; else if all approved -> APPROVED; else -> PENDING
        decisions = [ap.decision for ap in req.approvers]
        if any(d == 'REJECTED' for d in decisions):
            req.status = 'REJECTED'
        elif decisions and all(d == 'APPROVED' for d in decisions):
            req.status = 'APPROVED'
        else:
            req.status = 'PENDING'

    @app.post('/api/agent/submit')
    def agent_submit():
        # One-shot endpoint: upload artifacts and create bundle and request
        # Accepts multipart/form-data with files[] and a JSON field 'payload' containing request data
        payload_json = request.form.get('payload')
        files = request.files.getlist('files')
        if not payload_json:
            return jsonify({"error": "payload field required (JSON)"}), 400
        try:
            payload = app.json.loads(payload_json)
        except Exception:
            return jsonify({"error": "payload must be valid JSON"}), 400
        # Step 1: store artifacts
        artifacts = []
        for f in files:
            if not f.filename:
                continue
            filename = secure_filename(f.filename)
            stored_path, size = save_uploaded_file(f, app.config['STORAGE_DIR'])
            checksum = compute_checksum(stored_path)
            artifact = Artifact(filename=filename, path=stored_path, size=size, checksum=checksum)
            db.session.add(artifact)
            artifacts.append(artifact)
        # Also support URLs
        for url in (payload.get('artifact_urls') or []):
            art = fetch_url_to_artifact(url, app.config['STORAGE_DIR'])
            db.session.add(art)
            artifacts.append(art)
        if not artifacts:
            return jsonify({"error": "No artifacts provided"}), 400
        db.session.flush()
        # Step 2: bundle
        bundle = Bundle(name=payload.get('bundle_name') or f"bundle-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}")
        db.session.add(bundle)
        db.session.flush()
        for a in artifacts:
            db.session.execute(bundle_artifacts.insert().values(bundle_id=bundle.id, artifact_id=a.id))
        zip_path = create_bundle_zip(bundle, artifacts, app.config['STORAGE_DIR'])
        bundle.zip_path = zip_path
        # Step 3: request
        req = ApprovalRequest(bundle_id=bundle.id, title=payload.get('title') or 'Audit Approval Request', description=payload.get('description'), status='PENDING')
        if payload.get('due_in_days'):
            try:
                req.due_at = datetime.utcnow() + timedelta(days=int(payload['due_in_days']))
            except Exception:
                pass
        db.session.add(req)
        db.session.flush()
        created_approvers = []
        for ap in (payload.get('approvers') or []):
            email = (ap.get('email') or '').strip()
            name = (ap.get('name') or '').strip() or email
            if not email:
                continue
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            approver = Approver(request_id=req.id, email=email, name=name, token_hash=token_hash, decision='PENDING')
            db.session.add(approver)
            db.session.flush()
            created_approvers.append((approver, token))
        db.session.commit()
        # Notify
        if (payload.get('notify', True)) and created_approvers:
            for approver, token in created_approvers:
                approve_url = url_for('approval_form', request_id=req.id, token=token, _external=True)
                bundle_url = url_for('download_bundle', bundle_id=bundle.id, _external=True)
                notifier.send_request_email(approver.email, approver.name, req, approve_url, bundle_url)
        return jsonify({
            "bundle": bundle.to_dict(include_artifacts=True),
            "request": req.to_dict(include_approvers=True)
        })

    # Simple HTML approval page for human sign-off
    @app.get('/approve/<int:request_id>')
    def approval_form(request_id):
        token = request.args.get('token')
        if not token:
            return "Missing token", 400
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        req = ApprovalRequest.query.get_or_404(request_id)
        approver = Approver.query.filter_by(request_id=req.id, token_hash=token_hash).first()
        if not approver:
            return "Invalid or expired token", 403
        bundle_link = url_for('download_bundle', bundle_id=req.bundle_id)
        return render_template('approve.html', req=req, approver=approver, token=token, bundle_link=bundle_link)

    @app.post('/approve/<int:request_id>')
    def approval_submit(request_id):
        token = request.form.get('token')
        decision = (request.form.get('decision') or '').upper()
        signature_text = request.form.get('signature_text')
        comment = request.form.get('comment')
        if not token:
            return "Missing token", 400
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        req = ApprovalRequest.query.get_or_404(request_id)
        approver = Approver.query.filter_by(request_id=req.id, token_hash=token_hash).first()
        if not approver:
            return "Invalid token", 403
        if decision not in ('APPROVED', 'REJECTED'):
            return "Invalid decision", 400
        if approver.decision in ('APPROVED', 'REJECTED'):
            return "Decision already recorded", 400
        approver.decision = decision
        approver.signature_text = signature_text
        approver.comment = comment
        approver.signer_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        approver.approved_at = datetime.utcnow()
        _update_request_status(req)
        db.session.commit()
        return render_template('approve.html', req=req, approver=approver, token=token, bundle_link=url_for('download_bundle', bundle_id=req.bundle_id), success=True)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000'))) 



@app.route('/audit/submit', methods=['POST'])
def _auto_stub_audit_submit():
    return 'Auto-generated stub for /audit/submit', 200
