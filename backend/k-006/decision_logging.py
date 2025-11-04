import json
import logging
import os
from datetime import datetime
from uuid import uuid4
from flask import current_app, g, request
from database import db
from models import DecisionSession, DecisionEvent, Agent

class StructuredLogger:
    def __init__(self, name: str, log_file: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.propagate = False

        # Ensure logs directory
        dir_name = os.path.dirname(log_file)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_file) for h in self.logger.handlers):
            fh = logging.FileHandler(log_file)
            fh.setLevel(getattr(logging, level.upper(), logging.INFO))
            fh.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(fh)

    def log(self, level: str, event: dict):
        try:
            payload = json.dumps(event, default=str)
        except Exception as e:
            payload = json.dumps({"error": f"log_json_dump_failed: {e}", "raw": str(event)})
        self.logger.log(getattr(logging, level.upper(), logging.INFO), payload)


def get_correlation_id() -> str:
    # Try from request headers, then flask.g, else generate
    cid = None
    try:
        if hasattr(g, 'correlation_id') and g.correlation_id:
            cid = g.correlation_id
    except Exception:
        pass
    if not cid:
        try:
            if request:
                cid = request.headers.get('X-Correlation-Id')
        except Exception:
            pass
    if not cid:
        cid = uuid4().hex
    try:
        g.correlation_id = cid
    except Exception:
        pass
    return cid

class DecisionLogger:
    def __init__(self, app_logger: StructuredLogger):
        self.app_logger = app_logger
        self.session: DecisionSession | None = None

    def start_session(self, agent_id: str, user_id: str | None = None, correlation_id: str | None = None) -> DecisionSession:
        if correlation_id is None:
            correlation_id = get_correlation_id()
        # Ensure agent exists
        agent = Agent.query.get(agent_id)
        if not agent:
            agent = Agent(id=agent_id, name=agent_id, description="Auto-created agent")
            db.session.add(agent)
            db.session.commit()
        self.session = DecisionSession(
            id=str(uuid4()),
            agent_id=agent_id,
            user_id=user_id,
            correlation_id=correlation_id,
            status='running',
        )
        db.session.add(self.session)
        db.session.commit()
        self._write_log('INFO', 'SESSION_START', {
            'session_id': self.session.id,
            'agent_id': agent_id,
            'user_id': user_id,
            'correlation_id': correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
        })
        return self.session

    def _persist_event(self, type_: str, level: str = 'INFO', message: str | None = None, rationale: str | None = None, data: dict | None = None) -> DecisionEvent:
        if not self.session:
            raise RuntimeError('Decision session not started')
        ev = DecisionEvent(
            session_id=self.session.id,
            type=type_,
            level=level,
            message=message,
            rationale=rationale,
            data=data,
        )
        db.session.add(ev)
        db.session.commit()
        return ev

    def _write_log(self, level: str, event_type: str, payload: dict):
        cid = self.session.correlation_id if self.session else get_correlation_id()
        record = {
            'app': current_app.config.get('APP_NAME', 'agent-audit-app'),
            'level': level,
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': cid,
        }
        if self.session:
            record['session_id'] = self.session.id
            record['agent_id'] = self.session.agent_id
            record['user_id'] = self.session.user_id
        record.update(payload or {})
        self.app_logger.log(level, record)

    def log_input(self, input_data: dict | str):
        self._persist_event('INPUT', 'INFO', message='Input received', data={'input': input_data})
        self._write_log('INFO', 'INPUT', {'input': input_data})

    def log_context(self, context_data: dict, message: str | None = 'Context captured'):
        self._persist_event('CONTEXT', 'INFO', message=message, data=context_data)
        self._write_log('INFO', 'CONTEXT', {'message': message, 'context': context_data})

    def log_rationale(self, rationale: str, data: dict | None = None):
        self._persist_event('RATIONALE', 'INFO', message='Rationale noted', rationale=rationale, data=data)
        self._write_log('INFO', 'RATIONALE', {'rationale': rationale, 'data': data})

    def log_action(self, action: str, message: str | None = None, data: dict | None = None):
        self._persist_event('ACTION', 'INFO', message=message or f'Action: {action}', data={'action': action, **(data or {})})
        self._write_log('INFO', 'ACTION', {'action': action, 'message': message, 'data': data})

    def log_decision(self, decision: str, outcome: dict | None = None, rationale: str | None = None):
        self._persist_event('DECISION', 'INFO', message=decision, rationale=rationale, data={'outcome': outcome})
        self._write_log('INFO', 'DECISION', {'decision': decision, 'outcome': outcome, 'rationale': rationale})

    def log_error(self, error_message: str, data: dict | None = None):
        self._persist_event('ERROR', 'ERROR', message=error_message, data=data)
        self._write_log('ERROR', 'ERROR', {'error': error_message, 'data': data})

    def log(self, level: str, message: str, data: dict | None = None):
        self._persist_event('LOG', level.upper(), message=message, data=data)
        self._write_log(level.upper(), 'LOG', {'message': message, 'data': data})

    def finish_session(self, status: str = 'completed'):
        if not self.session:
            return
        self.session.status = status
        self.session.finished_at = datetime.utcnow()
        db.session.commit()
        self._write_log('INFO', 'SESSION_END', {
            'status': status,
            'finished_at': self.session.finished_at.isoformat(),
        })

