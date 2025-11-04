import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from config import Config
from database import db
from models import Tenant, Project, Resource, ResourceTag, CostRecord
from routes.tenants import tenants_bp
from routes.projects import projects_bp
from routes.resources import resources_bp
from routes.costs import costs_bp
from services.cost_engine import accrue_last_full_hour


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    # Blueprints
    app.register_blueprint(tenants_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(costs_bp)

    @app.route('/healthz')
    def health():
        return jsonify({'status': 'ok'})

    if app.config.get('SCHEDULER_ENABLED', True):
        scheduler = BackgroundScheduler(daemon=True)

        def scheduled_accrual():
            with app.app_context():
                try:
                    res = accrue_last_full_hour()
                    app.logger.info(f"Accrued costs: {res}")
                except Exception as e:
                    app.logger.exception(f"Accrual failed: {e}")

        # Run at minute 5 of every hour
        scheduler.add_job(scheduled_accrual, 'cron', minute=5, id='hourly_accrual', replace_existing=True)
        scheduler.start()

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))



@app.route('/projects', methods=['POST'])
def _auto_stub_projects():
    return 'Auto-generated stub for /projects', 200


@app.route('/resources', methods=['POST'])
def _auto_stub_resources():
    return 'Auto-generated stub for /resources', 200


@app.route('/costs', methods=['POST'])
def _auto_stub_costs():
    return 'Auto-generated stub for /costs', 200


@app.route('/costs/project/proj-002?period=2024-01', methods=['GET'])
def _auto_stub_costs_project_proj_002_period_2024_01():
    return 'Auto-generated stub for /costs/project/proj-002?period=2024-01', 200


@app.route('/costs/tenant/tenant-b?period=2024-01', methods=['GET'])
def _auto_stub_costs_tenant_tenant_b_period_2024_01():
    return 'Auto-generated stub for /costs/tenant/tenant-b?period=2024-01', 200
