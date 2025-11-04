import uuid
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON
from database import db


def _uuid():
    return str(uuid.uuid4())


class Scan(db.Model):
    __tablename__ = 'scans'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    target_url = db.Column(db.String(2048), nullable=False)
    scanner = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='queued')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    findings_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    metadata = db.Column(JSON, nullable=True)

    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=True)
    report = db.relationship('Report', backref=db.backref('scan', uselist=False))

    def to_dict(self, include_report_summary=False):
        data = {
            'id': self.id,
            'target_url': self.target_url,
            'scanner': self.scanner,
            'status': self.status,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'started_at': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'finished_at': self.finished_at.isoformat() + 'Z' if self.finished_at else None,
            'findings_count': self.findings_count,
            'error_message': self.error_message,
            'report_id': self.report_id,
            'metadata': self.metadata or {},
        }
        if include_report_summary and self.report:
            data['report_summary'] = {
                'high': self.report.severity_high,
                'medium': self.report.severity_medium,
                'low': self.report.severity_low,
                'info': self.report.severity_info,
                'created_at': self.report.created_at.isoformat() + 'Z' if self.report.created_at else None,
            }
        return data


class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    scan_id = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    title = db.Column(db.String(255), nullable=False, default='Automated Penetration Test Report')
    summary = db.Column(db.Text, nullable=True)
    details = db.Column(JSON, nullable=True)
    html = db.Column(db.Text, nullable=True)

    severity_high = db.Column(db.Integer, default=0)
    severity_medium = db.Column(db.Integer, default=0)
    severity_low = db.Column(db.Integer, default=0)
    severity_info = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'title': self.title,
            'summary': self.summary,
            'details': self.details or {},
            'severity': {
                'high': self.severity_high,
                'medium': self.severity_medium,
                'low': self.severity_low,
                'info': self.severity_info,
            },
        }

