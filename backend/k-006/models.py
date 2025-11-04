from datetime import datetime
import uuid
from database import db

class Agent(db.Model):
    __tablename__ = 'agents'
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat()
        }

class DecisionSession(db.Model):
    __tablename__ = 'decision_sessions'
    id = db.Column(db.String(36), primary_key=True)  # UUID4 string
    agent_id = db.Column(db.String(64), db.ForeignKey('agents.id'), nullable=False)
    user_id = db.Column(db.String(128), nullable=True)
    correlation_id = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), default='running', nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)

    agent = db.relationship('Agent')
    events = db.relationship('DecisionEvent', backref='session', lazy=True, order_by='DecisionEvent.timestamp')

    def to_dict(self, include_events=False):
        d = {
            "id": self.id,
            "agent": self.agent.to_dict() if self.agent else None,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None
        }
        if include_events:
            d["events"] = [e.to_dict() for e in self.events]
        return d

class DecisionEvent(db.Model):
    __tablename__ = 'decision_events'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('decision_sessions.id'), nullable=False)
    type = db.Column(db.String(32), nullable=False)  # INPUT, CONTEXT, RATIONALE, ACTION, DECISION, ERROR, LOG
    level = db.Column(db.String(16), default='INFO', nullable=False)
    message = db.Column(db.Text, nullable=True)
    rationale = db.Column(db.Text, nullable=True)
    data = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "type": self.type,
            "level": self.level,
            "message": self.message,
            "rationale": self.rationale,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

