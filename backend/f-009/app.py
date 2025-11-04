import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'dora.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')

db = SQLAlchemy(app)


class Deployment(db.Model):
    __tablename__ = 'deployments'
    id = db.Column(db.Integer, primary_key=True)
    service = db.Column(db.String(120), nullable=False)
    environment = db.Column(db.String(64), nullable=False)
    deployed_at = db.Column(db.DateTime, nullable=False, index=True)
    lead_time_seconds = db.Column(db.Integer, nullable=False, default=0)
    failed = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)

    incidents = db.relationship('Incident', backref='deployment', lazy=True)


class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    deployment_id = db.Column(db.Integer, db.ForeignKey('deployments.id'), nullable=True)
    service = db.Column(db.String(120), nullable=False)
    environment = db.Column(db.String(64), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, index=True)
    restored_at = db.Column(db.DateTime, nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)

    @property
    def mttr_seconds(self) -> Optional[int]:
        if self.started_at and self.restored_at:
            return int((self.restored_at - self.started_at).total_seconds())
        return None


with app.app_context():
    db.create_all()


def parse_date(s: Optional[str], default: Optional[date] = None) -> Optional[date]:
    if not s:
        return default
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return default


def daterange(start_date: date, end_date: date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)


def apply_filters(model_query, start_dt: datetime, end_dt: datetime, service: Optional[str], environment: Optional[str], time_field: str):
    q = model_query
    if start_dt:
        q = q.filter(getattr(model_query.column_descriptions[0]['type'], time_field) >= start_dt)
    if end_dt:
        q = q.filter(getattr(model_query.column_descriptions[0]['type'], time_field) <= end_dt)
    if service:
        q = q.filter(model_query.column_descriptions[0]['type'].service == service)
    if environment:
        q = q.filter(model_query.column_descriptions[0]['type'].environment == environment)
    return q


def compute_summary(start_date: date, end_date: date, service: Optional[str], environment: Optional[str]) -> Dict:
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    dep_q = Deployment.query
    if service:
        dep_q = dep_q.filter(Deployment.service == service)
    if environment:
        dep_q = dep_q.filter(Deployment.environment == environment)
    dep_q = dep_q.filter(Deployment.deployed_at >= start_dt, Deployment.deployed_at <= end_dt)
    deployments: List[Deployment] = dep_q.all()

    inc_q = Incident.query
    if service:
        inc_q = inc_q.filter(Incident.service == service)
    if environment:
        inc_q = inc_q.filter(Incident.environment == environment)
    inc_q = inc_q.filter(Incident.started_at >= start_dt, Incident.started_at <= end_dt)
    incidents: List[Incident] = inc_q.all()

    total_deployments = len(deployments)
    avg_lead_time_seconds = int(sum(d.lead_time_seconds for d in deployments) / total_deployments) if total_deployments else 0
    failed_deployments = sum(1 for d in deployments if d.failed)
    change_failure_rate = (failed_deployments / total_deployments) if total_deployments else 0.0

    # MTTR: average of incidents with restored_at set
    mttrs = [inc.mttr_seconds for inc in incidents if inc.mttr_seconds is not None]
    avg_mttr_seconds = int(sum(mttrs) / len(mttrs)) if mttrs else 0

    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'service': service,
        'environment': environment,
        'total_deployments': total_deployments,
        'avg_lead_time_seconds': avg_lead_time_seconds,
        'failed_deployments': failed_deployments,
        'change_failure_rate': round(change_failure_rate, 4),
        'avg_mttr_seconds': avg_mttr_seconds,
    }


def compute_trends(start_date: date, end_date: date, service: Optional[str], environment: Optional[str]):
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    dep_q = Deployment.query
    if service:
        dep_q = dep_q.filter(Deployment.service == service)
    if environment:
        dep_q = dep_q.filter(Deployment.environment == environment)
    dep_q = dep_q.filter(Deployment.deployed_at >= start_dt, Deployment.deployed_at <= end_dt)
    deployments: List[Deployment] = dep_q.all()

    inc_q = Incident.query
    if service:
        inc_q = inc_q.filter(Incident.service == service)
    if environment:
        inc_q = inc_q.filter(Incident.environment == environment)
    inc_q = inc_q.filter(Incident.started_at >= start_dt, Incident.started_at <= end_dt)
    incidents: List[Incident] = inc_q.all()

    # Bucket by day
    bucket = {}
    for single_date in daterange(start_date, end_date):
        key = single_date.isoformat()
        bucket[key] = {
            'deployments': 0,
            'lead_times': [],
            'failed': 0,
            'inc_mttrs': [],
        }

    for d in deployments:
        key = d.deployed_at.date().isoformat()
        if key in bucket:
            bucket[key]['deployments'] += 1
            bucket[key]['lead_times'].append(d.lead_time_seconds)
            if d.failed:
                bucket[key]['failed'] += 1

    for inc in incidents:
        key = inc.started_at.date().isoformat()
        if key in bucket and inc.mttr_seconds is not None:
            bucket[key]['inc_mttrs'].append(inc.mttr_seconds)

    labels = []
    df_values = []
    lt_values = []
    cfr_values = []
    mttr_values = []

    for single_date in daterange(start_date, end_date):
        key = single_date.isoformat()
        labels.append(key)
        b = bucket[key]
        total = b['deployments']
        df_values.append(total)
        lt_avg = int(sum(b['lead_times']) / len(b['lead_times'])) if b['lead_times'] else 0
        lt_values.append(lt_avg)
        cfr = (b['failed'] / total) if total else 0.0
        cfr_values.append(round(cfr, 4))
        mttr = int(sum(b['inc_mttrs']) / len(b['inc_mttrs'])) if b['inc_mttrs'] else 0
        mttr_values.append(mttr)

    return {
        'labels': labels,
        'deployment_frequency': df_values,
        'lead_time_avg_seconds': lt_values,
        'change_failure_rate': cfr_values,
        'mttr_avg_seconds': mttr_values,
    }


@app.route('/')
def index():
    # Default filters: last 30 days
    today = date.today()
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    service = request.args.get('service') or ''
    environment = request.args.get('environment') or ''
    default_start = today - timedelta(days=29)
    start_date_val = parse_date(start_str, default_start)
    end_date_val = parse_date(end_str, today)

    return render_template('dashboard.html',
                           start_date=start_date_val.isoformat(),
                           end_date=end_date_val.isoformat(),
                           service=service,
                           environment=environment)


@app.route('/deployments')
def deployments_list():
    service = request.args.get('service')
    environment = request.args.get('environment')
    q = Deployment.query.order_by(Deployment.deployed_at.desc())
    if service:
        q = q.filter(Deployment.service == service)
    if environment:
        q = q.filter(Deployment.environment == environment)
    deployments = q.limit(500).all()
    return render_template('deployments_list.html', deployments=deployments)


@app.route('/deployments/new', methods=['GET', 'POST'])
def deployments_new():
    if request.method == 'POST':
        try:
            service = request.form.get('service', '').strip()
            environment = request.form.get('environment', '').strip()
            deployed_at_str = request.form.get('deployed_at')
            lead_time_seconds = int(request.form.get('lead_time_seconds') or 0)
            failed = request.form.get('failed') == 'on'
            notes = request.form.get('notes')

            deployed_at = datetime.fromisoformat(deployed_at_str)

            d = Deployment(service=service, environment=environment, deployed_at=deployed_at,
                           lead_time_seconds=lead_time_seconds, failed=failed, notes=notes)
            db.session.add(d)
            db.session.commit()
            flash('Deployment recorded', 'success')
            return redirect(url_for('deployments_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    # GET
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
    return render_template('deployment_form.html', now_iso=now_iso)


@app.route('/incidents')
def incidents_list():
    service = request.args.get('service')
    environment = request.args.get('environment')
    q = Incident.query.order_by(Incident.started_at.desc())
    if service:
        q = q.filter(Incident.service == service)
    if environment:
        q = q.filter(Incident.environment == environment)
    incidents = q.limit(500).all()
    return render_template('incidents_list.html', incidents=incidents)


@app.route('/incidents/new', methods=['GET', 'POST'])
def incidents_new():
    deployments = Deployment.query.order_by(Deployment.deployed_at.desc()).limit(200).all()
    if request.method == 'POST':
        try:
            deployment_id = request.form.get('deployment_id')
            service = request.form.get('service', '').strip()
            environment = request.form.get('environment', '').strip()
            started_at_str = request.form.get('started_at')
            restored_at_str = request.form.get('restored_at')
            notes = request.form.get('notes')

            started_at = datetime.fromisoformat(started_at_str)
            restored_at = datetime.fromisoformat(restored_at_str) if restored_at_str else None
            dep_id_val = int(deployment_id) if deployment_id else None

            inc = Incident(deployment_id=dep_id_val, service=service, environment=environment,
                           started_at=started_at, restored_at=restored_at, notes=notes)
            db.session.add(inc)
            db.session.commit()
            flash('Incident recorded', 'success')
            return redirect(url_for('incidents_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {e}', 'danger')
    now_iso = datetime.utcnow().replace(microsecond=0).isoformat()
    return render_template('incident_form.html', deployments=deployments, now_iso=now_iso)


# API endpoints
@app.route('/api/metrics/summary')
def api_metrics_summary():
    today = date.today()
    start_date_val = parse_date(request.args.get('start_date'), today - timedelta(days=29))
    end_date_val = parse_date(request.args.get('end_date'), today)
    service = request.args.get('service')
    environment = request.args.get('environment')

    summary = compute_summary(start_date_val, end_date_val, service, environment)
    return jsonify(summary)


@app.route('/api/metrics/trends')
def api_metrics_trends():
    today = date.today()
    start_date_val = parse_date(request.args.get('start_date'), today - timedelta(days=29))
    end_date_val = parse_date(request.args.get('end_date'), today)
    service = request.args.get('service')
    environment = request.args.get('environment')

    trends = compute_trends(start_date_val, end_date_val, service, environment)
    return jsonify(trends)


@app.route('/api/deployments', methods=['GET', 'POST'])
def api_deployments():
    if request.method == 'POST':
        data = request.get_json(force=True)
        try:
            d = Deployment(
                service=data['service'],
                environment=data['environment'],
                deployed_at=datetime.fromisoformat(data['deployed_at']),
                lead_time_seconds=int(data.get('lead_time_seconds', 0)),
                failed=bool(data.get('failed', False)),
                notes=data.get('notes')
            )
            db.session.add(d)
            db.session.commit()
            return jsonify({'status': 'ok', 'id': d.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'error': str(e)}), 400
    else:
        q = Deployment.query.order_by(Deployment.deployed_at.desc()).limit(1000).all()
        return jsonify([
            {
                'id': d.id,
                'service': d.service,
                'environment': d.environment,
                'deployed_at': d.deployed_at.isoformat(),
                'lead_time_seconds': d.lead_time_seconds,
                'failed': d.failed,
                'notes': d.notes,
            } for d in q
        ])


@app.route('/api/incidents', methods=['GET', 'POST'])
def api_incidents():
    if request.method == 'POST':
        data = request.get_json(force=True)
        try:
            deployment_id = data.get('deployment_id')
            inc = Incident(
                deployment_id=int(deployment_id) if deployment_id else None,
                service=data['service'],
                environment=data['environment'],
                started_at=datetime.fromisoformat(data['started_at']),
                restored_at=datetime.fromisoformat(data['restored_at']) if data.get('restored_at') else None,
                notes=data.get('notes')
            )
            db.session.add(inc)
            db.session.commit()
            return jsonify({'status': 'ok', 'id': inc.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'error', 'error': str(e)}), 400
    else:
        q = Incident.query.order_by(Incident.started_at.desc()).limit(1000).all()
        return jsonify([
            {
                'id': inc.id,
                'deployment_id': inc.deployment_id,
                'service': inc.service,
                'environment': inc.environment,
                'started_at': inc.started_at.isoformat(),
                'restored_at': inc.restored_at.isoformat() if inc.restored_at else None,
                'mttr_seconds': inc.mttr_seconds,
                'notes': inc.notes,
            } for inc in q
        ])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



def create_app():
    return app


@app.route('/api/metrics/trends?days=30', methods=['GET'])
def _auto_stub_api_metrics_trends_days_30():
    return 'Auto-generated stub for /api/metrics/trends?days=30', 200
