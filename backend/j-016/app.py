import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import Config
from db import db
from models import *  # noqa
from routes.teams import bp as teams_bp
from routes.routes import bp as routes_bp
from routes.events import bp as events_bp
from routes.deliveries import bp as deliveries_bp
from services.delivery import send_pending_deliveries
from services.digest import run_digests_once

scheduler = BackgroundScheduler()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(teams_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(deliveries_bp)

    @app.get('/')
    def health():
        return jsonify({'ok': True, 'service': 'notification-center', 'version': '1.0.0'})

    # Scheduler jobs
    scheduler.add_job(lambda: _safe_job('deliver_pending', send_pending_deliveries),
                      trigger=IntervalTrigger(seconds=Config.DELIVERY_INTERVAL_SECONDS), id='deliver_pending', replace_existing=True)
    scheduler.add_job(lambda: _safe_job('run_digests', run_digests_once),
                      trigger=IntervalTrigger(seconds=Config.DIGEST_CHECK_INTERVAL_SECONDS), id='run_digests', replace_existing=True)
    scheduler.start()

    return app


def _safe_job(name, fn):
    try:
        result = fn()
        # Could log result
        return result
    except Exception as e:
        # Basic stderr logging
        print(f"Job {name} failed: {e}")
        return None


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/notifications', methods=['POST'])
def _auto_stub_notifications():
    return 'Auto-generated stub for /notifications', 200
