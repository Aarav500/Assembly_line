from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
import json


db = SQLAlchemy()


class Incident(db.Model):
    __tablename__ = 'incidents'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='unknown')
    impact = db.Column(db.Text, nullable=True)

    # Store JSON fields as TEXT for portability; keep helpers to parse/serialize
    timeline_raw = db.Column('timeline', db.Text, nullable=True)
    contributing_factors_raw = db.Column('contributing_factors', db.Text, nullable=True)
    action_items_raw = db.Column('action_items', db.Text, nullable=True)

    root_cause_hypothesis = db.Column(db.Text, nullable=True)
    detection = db.Column(db.Text, nullable=True)
    remediation = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(40), nullable=False, default='draft')

    raw_input = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)

    llm_model = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    @property
    def timeline(self):
        try:
            return json.loads(self.timeline_raw) if self.timeline_raw else []
        except Exception:
            return []

    @timeline.setter
    def timeline(self, value):
        self.timeline_raw = json.dumps(value or [])

    @property
    def contributing_factors(self):
        try:
            return json.loads(self.contributing_factors_raw) if self.contributing_factors_raw else []
        except Exception:
            return []

    @contributing_factors.setter
    def contributing_factors(self, value):
        self.contributing_factors_raw = json.dumps(value or [])

    @property
    def action_items(self):
        try:
            return json.loads(self.action_items_raw) if self.action_items_raw else []
        except Exception:
            return []

    @action_items.setter
    def action_items(self, value):
        self.action_items_raw = json.dumps(value or [])

    def to_dict(self, summary_only: bool = False):
        data = {
            'id': self.id,
            'title': self.title,
            'summary': self.summary,
            'severity': self.severity,
            'impact': self.impact,
            'timeline': self.timeline,
            'root_cause_hypothesis': self.root_cause_hypothesis,
            'contributing_factors': self.contributing_factors,
            'detection': self.detection,
            'remediation': self.remediation,
            'action_items': self.action_items,
            'status': self.status,
            'llm_model': self.llm_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if not summary_only:
            data['raw_input'] = self.raw_input
            data['context'] = self.context
        return data

