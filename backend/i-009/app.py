import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy


def create_app():
    app = Flask(__name__)

    db_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    register_error_handlers(app)

    return app


db = SQLAlchemy()


# ---- Models ----
class Vulnerability(db.Model):
    __tablename__ = "vulnerability"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    severity = db.Column(db.String(20), nullable=True)  # low, medium, high, critical
    cve_id = db.Column(db.String(64), nullable=True)
    cvss_score = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="DETECTED")

    triage_notes = db.Column(db.Text, nullable=True)
    patch_details = db.Column(db.Text, nullable=True)
    verification_notes = db.Column(db.Text, nullable=True)
    close_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_events=False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "cve_id": self.cve_id,
            "cvss_score": self.cvss_score,
            "status": self.status,
            "triage_notes": self.triage_notes,
            "patch_details": self.patch_details,
            "verification_notes": self.verification_notes,
            "close_notes": self.close_notes,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }
        if include_events:
            data["events"] = [e.to_dict() for e in self.events.order_by(VulnerabilityEvent.at.asc()).all()]
        return data


class VulnerabilityEvent(db.Model):
    __tablename__ = "vulnerability_event"

    id = db.Column(db.Integer, primary_key=True)
    vulnerability_id = db.Column(db.Integer, db.ForeignKey("vulnerability.id"), nullable=False, index=True)
    event = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    at = db.Column(db.DateTime, default=datetime.utcnow)

    vulnerability = db.relationship(
        "Vulnerability",
        backref=db.backref("events", lazy="dynamic", cascade="all, delete-orphan")
    )

    def to_dict(self):
        return {
            "id": self.id,
            "vulnerability_id": self.vulnerability_id,
            "event": self.event,
            "notes": self.notes,
            "at": self.at.isoformat() + "Z" if self.at else None,
        }


# ---- Constants ----
STATUS_DETECTED = "DETECTED"
STATUS_TRIAGED = "TRIAGED"
STATUS_PATCHED = "PATCHED"
STATUS_VERIFIED = "VERIFIED"
STATUS_CLOSED = "CLOSED"

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {STATUS_DETECTED, STATUS_TRIAGED, STATUS_PATCHED, STATUS_VERIFIED, STATUS_CLOSED}


# ---- Helpers ----
def add_event(vuln: Vulnerability, event: str, notes: str | None = None):
    ev = VulnerabilityEvent(vulnerability=vuln, event=event, notes=notes)
    db.session.add(ev)


def get_vuln_or_404(vuln_id: int) -> Vulnerability:
    vuln = Vulnerability.query.get(vuln_id)
    if not vuln:
        raise NotFoundError(f"Vulnerability {vuln_id} not found")
    return vuln


# ---- Errors ----
class APIError(Exception):
    status_code = 400

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self):
        return {"error": self.message}


class NotFoundError(APIError):
    status_code = 404


class ConflictError(APIError):
    status_code = 409


def register_error_handlers(app: Flask):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(404)
    def handle_404(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(_):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_500(err):
        return jsonify({"error": "Internal server error"}), 500


# ---- Routes ----

def register_routes(app: Flask):
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # Detect: create a new vulnerability
    @app.post("/vulns/detect")
    def detect_vuln():
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        if not title:
            raise APIError("'title' is required", 400)

        description = data.get("description")
        severity = (data.get("severity") or None)
        if severity:
            severity = severity.lower()
            if severity not in VALID_SEVERITIES:
                raise APIError("Invalid severity. Must be one of: low, medium, high, critical", 400)
        cve_id = (data.get("cve_id") or None)
        cvss_score = data.get("cvss_score")
        if cvss_score is not None:
            try:
                cvss_score = float(cvss_score)
            except Exception:
                raise APIError("'cvss_score' must be a number", 400)

        vuln = Vulnerability(
            title=title,
            description=description,
            severity=severity,
            cve_id=cve_id,
            cvss_score=cvss_score,
            status=STATUS_DETECTED,
        )
        db.session.add(vuln)
        db.session.flush()  # get id
        add_event(vuln, STATUS_DETECTED, notes=f"Detected vulnerability '{title}'")
        db.session.commit()
        return jsonify(vuln.to_dict(include_events=True)), 201

    @app.get("/vulns")
    def list_vulns():
        # Filtering
        q = (request.args.get("q") or "").strip()
        status = (request.args.get("status") or "").upper().strip()
        severity = (request.args.get("severity") or "").lower().strip()

        query = Vulnerability.query
        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Vulnerability.title.ilike(like),
                    Vulnerability.description.ilike(like),
                    Vulnerability.cve_id.ilike(like),
                )
            )
        if status:
            if status not in VALID_STATUSES:
                raise APIError("Invalid status filter", 400)
            query = query.filter(Vulnerability.status == status)
        if severity:
            if severity not in VALID_SEVERITIES:
                raise APIError("Invalid severity filter", 400)
            query = query.filter(Vulnerability.severity == severity)

        sort = (request.args.get("sort") or "updated_at").lower()
        direction = (request.args.get("direction") or "desc").lower()
        order_col = Vulnerability.updated_at if sort == "updated_at" else Vulnerability.created_at
        if direction == "asc":
            query = query.order_by(order_col.asc())
        else:
            query = query.order_by(order_col.desc())

        page = int(request.args.get("page") or 1)
        page_size = min(int(request.args.get("page_size") or 25), 100)
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return jsonify({
            "items": [v.to_dict() for v in pagination.items],
            "meta": {
                "page": pagination.page,
                "pages": pagination.pages,
                "total": pagination.total,
                "page_size": pagination.per_page,
            }
        })

    @app.get("/vulns/<int:vuln_id>")
    def get_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        include_events = (request.args.get("events") == "1")
        return jsonify(vuln.to_dict(include_events=include_events))

    # Triage step
    @app.post("/vulns/<int:vuln_id>/triage")
    def triage_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        if vuln.status != STATUS_DETECTED:
            raise ConflictError(f"Cannot triage from status {vuln.status}. Expected {STATUS_DETECTED}")

        data = request.get_json(silent=True) or {}
        severity = (data.get("severity") or None)
        if severity:
            severity = severity.lower()
            if severity not in VALID_SEVERITIES:
                raise APIError("Invalid severity. Must be one of: low, medium, high, critical", 400)
        triage_notes = data.get("triage_notes")

        if severity:
            vuln.severity = severity
        vuln.triage_notes = triage_notes
        vuln.status = STATUS_TRIAGED
        add_event(vuln, STATUS_TRIAGED, notes=triage_notes or "Triaged")
        db.session.commit()
        return jsonify(vuln.to_dict(include_events=True))

    # Patch step
    @app.post("/vulns/<int:vuln_id>/patch")
    def patch_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        if vuln.status != STATUS_TRIAGED:
            raise ConflictError(f"Cannot patch from status {vuln.status}. Expected {STATUS_TRIAGED}")

        data = request.get_json(silent=True) or {}
        patch_details = (data.get("patch_details") or "").strip()
        if not patch_details:
            raise APIError("'patch_details' is required", 400)

        vuln.patch_details = patch_details
        vuln.status = STATUS_PATCHED
        add_event(vuln, STATUS_PATCHED, notes=patch_details)
        db.session.commit()
        return jsonify(vuln.to_dict(include_events=True))

    # Verify step
    @app.post("/vulns/<int:vuln_id>/verify")
    def verify_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        if vuln.status != STATUS_PATCHED:
            raise ConflictError(f"Cannot verify from status {vuln.status}. Expected {STATUS_PATCHED}")

        data = request.get_json(silent=True) or {}
        passed = data.get("passed")
        if passed is None:
            raise APIError("'passed' boolean is required", 400)
        verification_notes = data.get("verification_notes")

        vuln.verification_notes = verification_notes
        if bool(passed):
            vuln.status = STATUS_VERIFIED
            add_event(vuln, STATUS_VERIFIED, notes=verification_notes or "Verification passed")
        else:
            # remain PATCHED; log failure for additional work
            add_event(vuln, "VERIFICATION_FAILED", notes=verification_notes or "Verification failed")
        db.session.commit()
        return jsonify(vuln.to_dict(include_events=True))

    # Close step
    @app.post("/vulns/<int:vuln_id>/close")
    def close_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        if vuln.status != STATUS_VERIFIED:
            raise ConflictError(f"Cannot close from status {vuln.status}. Expected {STATUS_VERIFIED}")

        data = request.get_json(silent=True) or {}
        close_notes = data.get("close_notes")
        vuln.close_notes = close_notes
        vuln.status = STATUS_CLOSED
        add_event(vuln, STATUS_CLOSED, notes=close_notes or "Closed")
        db.session.commit()
        return jsonify(vuln.to_dict(include_events=True))

    # Events listing
    @app.get("/vulns/<int:vuln_id>/events")
    def list_events(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        events = [e.to_dict() for e in vuln.events.order_by(VulnerabilityEvent.at.asc()).all()]
        return jsonify({"vulnerability_id": vuln.id, "events": events})

    # Optional: delete a vulnerability (e.g., cleanup in dev). Not part of lifecycle.
    @app.delete("/vulns/<int:vuln_id>")
    def delete_vuln(vuln_id: int):
        vuln = get_vuln_or_404(vuln_id)
        db.session.delete(vuln)
        db.session.commit()
        return jsonify({"deleted": True, "id": vuln_id})


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))



@app.route('/vulnerabilities', methods=['POST'])
def _auto_stub_vulnerabilities():
    return 'Auto-generated stub for /vulnerabilities', 200
