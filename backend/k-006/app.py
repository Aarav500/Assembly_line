import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import os
from uuid import uuid4
from datetime import datetime
from flask import Flask, request, jsonify, g
from config import Config
from database import init_db, db
from models import Agent, DecisionSession, DecisionEvent
from decision_logging import StructuredLogger, DecisionLogger, get_correlation_id
from agent import AgentEngine


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Init DB
    init_db(app)

    # Structured file logger
    app_logger = StructuredLogger(
        name='audit',
        log_file=app.config['JSON_LOG_FILE'],
        level=app.config.get('LOG_LEVEL', 'INFO')
    )

    # Seed a default agent if not exists
    with app.app_context():
        if not Agent.query.get('default-agent'):
            db.session.add(Agent(id='default-agent', name='Default Agent', description='Baseline agent for demo'))
            db.session.commit()

    @app.before_request
    def before_request():
        # Correlation ID management
        corr = request.headers.get('X-Correlation-Id') or uuid4().hex
        g.correlation_id = corr
        # Log incoming request
        try:
            payload = request.get_json(silent=True)
        except Exception:
            payload = None
        app_logger.log('INFO', {
            'app': app.config.get('APP_NAME', 'agent-audit-app'),
            'event_type': 'HTTP_REQUEST',
            'method': request.method,
            'path': request.path,
            'query': request.args.to_dict(flat=False),
            'body': payload,
            'correlation_id': corr,
            'timestamp': datetime.utcnow().isoformat(),
        })

    @app.after_request
    def after_request(response):
        response.headers['X-Correlation-Id'] = getattr(g, 'correlation_id', '')
        app_logger.log('INFO', {
            'app': app.config.get('APP_NAME', 'agent-audit-app'),
            'event_type': 'HTTP_RESPONSE',
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'correlation_id': getattr(g, 'correlation_id', None),
            'timestamp': datetime.utcnow().isoformat(),
        })
        return response

    @app.get('/health')
    def health():
        return jsonify({
            'status': 'ok',
            'time': datetime.utcnow().isoformat(),
            'app': app.config.get('APP_NAME', 'agent-audit-app')
        })

    @app.post('/agent/run')
    def run_agent():
        data = request.get_json(silent=True) or {}
        agent_id = data.get('agent_id', 'default-agent')
        user_id = data.get('user_id')
        input_payload = data.get('input') if 'input' in data else data

        decision_logger = DecisionLogger(app_logger)
        session = decision_logger.start_session(agent_id=agent_id, user_id=user_id, correlation_id=getattr(g, 'correlation_id', None))

        engine = AgentEngine(agent_id=agent_id)
        result = {}
        try:
            result = engine.run(input_payload=input_payload, decision_logger=decision_logger)
            decision_logger.finish_session('completed')
        except Exception as e:
            decision_logger.log_error(str(e))
            decision_logger.finish_session('failed')
            response = jsonify({'error': 'Agent execution failed', 'details': str(e), 'session_id': session.id})
            response.status_code = 500
            return response

        # Fetch complete trail
        session = DecisionSession.query.get(session.id)
        response = {
            'session': session.to_dict(include_events=True),
            'result': result
        }
        return jsonify(response)

    @app.get('/audit/sessions')
    def list_sessions():
        # Optional filters
        agent_id = request.args.get('agent_id')
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        q = DecisionSession.query
        if agent_id:
            q = q.filter(DecisionSession.agent_id == agent_id)
        if user_id:
            q = q.filter(DecisionSession.user_id == user_id)
        if status:
            q = q.filter(DecisionSession.status == status)
        q = q.order_by(DecisionSession.started_at.desc())

        items = q.offset(offset).limit(min(limit, 200)).all()
        return jsonify({'items': [s.to_dict(include_events=False) for s in items], 'count': len(items)})

    @app.get('/audit/sessions/<session_id>')
    def get_session(session_id: str):
        s = DecisionSession.query.get(session_id)
        if not s:
            return jsonify({'error': 'not_found'}), 404
        return jsonify(s.to_dict(include_events=True))

    @app.get('/audit/sessions/<session_id>/events')
    def get_session_events(session_id: str):
        s = DecisionSession.query.get(session_id)
        if not s:
            return jsonify({'error': 'not_found'}), 404
        return jsonify({'events': [e.to_dict() for e in s.events]})

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port)



@app.route('/agent/decision', methods=['POST'])
def _auto_stub_agent_decision():
    return 'Auto-generated stub for /agent/decision', 200


@app.route('/agent/trail', methods=['GET'])
def _auto_stub_agent_trail():
    return 'Auto-generated stub for /agent/trail', 200


@app.route('/agent/trail?agent_id=agent-001', methods=['GET'])
def _auto_stub_agent_trail_agent_id_agent_001():
    return 'Auto-generated stub for /agent/trail?agent_id=agent-001', 200
