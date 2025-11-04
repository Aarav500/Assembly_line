import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from models import db, Incident
from llm import LLMClient


def create_app():
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True, static_url_path='/static', static_folder='static')

    os.makedirs(app.instance_path, exist_ok=True)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(app.instance_path, 'app.db')}")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JSON_SORT_KEYS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    llm_client = LLMClient()

    @app.get('/healthz')
    def healthz():
        return jsonify({"ok": True})

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.post('/api/report')
    def create_report():
        payload = request.get_json(silent=True) or {}

        raw_input = (payload.get('raw_input') or '').strip()
        context = (payload.get('context') or '').strip()
        severity = (payload.get('severity') or '').strip() or 'unknown'
        status = (payload.get('status') or '').strip() or 'draft'

        if not raw_input:
            return jsonify({"error": "raw_input is required"}), 400

        try:
            report, model_used = llm_client.generate_incident_report(
                raw_input=raw_input,
                context=context,
                severity=severity
            )
        except Exception as e:
            return jsonify({"error": f"Failed to generate report: {e}"}), 500

        inc = Incident(
            title=report.get('title'),
            summary=report.get('summary'),
            severity=report.get('severity') or severity,
            impact=report.get('impact'),
            timeline=report.get('timeline'),
            root_cause_hypothesis=report.get('root_cause_hypothesis'),
            contributing_factors=report.get('contributing_factors'),
            detection=report.get('detection'),
            remediation=report.get('remediation'),
            action_items=report.get('action_items'),
            status=report.get('status') or status,
            raw_input=raw_input,
            context=context,
            llm_model=model_used,
        )
        db.session.add(inc)
        db.session.commit()

        return jsonify({"incident": inc.to_dict()}), 201

    @app.get('/api/report/<int:incident_id>')
    def get_report(incident_id: int):
        inc = Incident.query.get_or_404(incident_id)
        return jsonify({"incident": inc.to_dict()})

    @app.get('/api/reports')
    def list_reports():
        # Simple listing endpoint with optional severity/status filters
        severity = request.args.get('severity')
        status = request.args.get('status')
        q = Incident.query
        if severity:
            q = q.filter(Incident.severity.ilike(severity))
        if status:
            q = q.filter(Incident.status.ilike(status))
        items = [i.to_dict(summary_only=True) for i in q.order_by(Incident.created_at.desc()).limit(100).all()]
        return jsonify({"incidents": items})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), debug=os.getenv('FLASK_DEBUG', '0') == '1')



@app.route('/incidents', methods=['GET', 'POST'])
def _auto_stub_incidents():
    return 'Auto-generated stub for /incidents', 200
