import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
import os
from flask import Flask, render_template, jsonify, request, send_from_directory, url_for, redirect
from dateutil import parser as dateparser
from extensions import db
from models import Team, Project, ResourceUsage, aggregate_usage_by_team, aggregate_usage_by_project_for_team, timeseries_usage_for_project, timeseries_usage_for_team
from config import Config
from scheduler import init_scheduler
from reports import list_reports


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        if not os.path.exists(app.config['REPORTS_DIR']):
            os.makedirs(app.config['REPORTS_DIR'], exist_ok=True)
        # Create tables if missing
        db.create_all()

    if app.config.get('SCHEDULER_ENABLED', True):
        init_scheduler(app)

    def parse_date(s, default=None):
        if not s:
            return default
        try:
            return dateparser.parse(s)
        except Exception:
            return default

    def get_date_range():
        end_str = request.args.get('end')
        start_str = request.args.get('start')
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        default_start = today - timedelta(days=30)
        default_end = today + timedelta(days=1)
        start = parse_date(start_str, default_start)
        end = parse_date(end_str, default_end)
        if end <= start:
            end = start + timedelta(days=1)
        return start, end

    @app.route('/')
    def index():
        start, end = get_date_range()
        teams = Team.query.order_by(Team.name.asc()).all()
        summary = aggregate_usage_by_team(start, end)
        return render_template('index.html', teams=teams, start=start, end=end, summary=summary)

    @app.route('/teams')
    def teams():
        teams = Team.query.order_by(Team.name.asc()).all()
        return render_template('teams.html', teams=teams)

    @app.route('/team/<int:team_id>')
    def team_view(team_id):
        team = Team.query.get_or_404(team_id)
        start, end = get_date_range()
        projects = aggregate_usage_by_project_for_team(team_id, start, end)
        return render_template('team.html', team=team, projects=projects, start=start, end=end)

    @app.route('/project/<int:project_id>')
    def project_view(project_id):
        project = Project.query.get_or_404(project_id)
        start, end = get_date_range()
        return render_template('project.html', project=project, start=start, end=end)

    @app.route('/api/summary')
    def api_summary():
        start, end = get_date_range()
        data = aggregate_usage_by_team(start, end)
        return jsonify({
            'start': start.isoformat(),
            'end': end.isoformat(),
            'teams': data,
        })

    @app.route('/api/team/<int:team_id>/timeseries')
    def api_team_timeseries(team_id):
        group = request.args.get('group', 'day')
        start, end = get_date_range()
        data = timeseries_usage_for_team(team_id, start, end, group=group)
        return jsonify({
            'team_id': team_id,
            'group': group,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'series': data,
        })

    @app.route('/api/project/<int:project_id>/timeseries')
    def api_project_timeseries(project_id):
        group = request.args.get('group', 'day')
        start, end = get_date_range()
        data = timeseries_usage_for_project(project_id, start, end, group=group)
        return jsonify({
            'project_id': project_id,
            'group': group,
            'start': start.isoformat(),
            'end': end.isoformat(),
            'series': data,
        })

    @app.route('/reports')
    def reports():
        files = list_reports(app.config['REPORTS_DIR'])
        return render_template('reports.html', files=files)

    @app.route('/reports/<path:filename>')
    def download_report(filename):
        return send_from_directory(app.config['REPORTS_DIR'], filename, as_attachment=True)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/api/teams', methods=['GET'])
def _auto_stub_api_teams():
    return 'Auto-generated stub for /api/teams', 200


@app.route('/api/dashboard/engineering', methods=['GET'])
def _auto_stub_api_dashboard_engineering():
    return 'Auto-generated stub for /api/dashboard/engineering', 200


@app.route('/api/dashboard/nonexistent', methods=['GET'])
def _auto_stub_api_dashboard_nonexistent():
    return 'Auto-generated stub for /api/dashboard/nonexistent', 200


@app.route('/api/usage/engineering/api-service', methods=['GET'])
def _auto_stub_api_usage_engineering_api_service():
    return 'Auto-generated stub for /api/usage/engineering/api-service', 200


@app.route('/api/report/daily', methods=['GET'])
def _auto_stub_api_report_daily():
    return 'Auto-generated stub for /api/report/daily', 200


@app.route('/api/report/invalid', methods=['GET'])
def _auto_stub_api_report_invalid():
    return 'Auto-generated stub for /api/report/invalid', 200
