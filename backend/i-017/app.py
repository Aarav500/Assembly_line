import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from config import Config
from models import db, ensure_default_policy
from routes import privacy_bp
from privacy import run_retention_once
from security import require_env_secrets


def create_app():
    load_dotenv()
    require_env_secrets()

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_default_policy()

    app.register_blueprint(privacy_bp)

    @app.after_request
    def apply_privacy_security_headers(resp):
        # Strict, privacy-first defaults
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'DENY'
        resp.headers['Referrer-Policy'] = 'no-referrer'
        resp.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), usb=(), payment=()'
        )
        # Conservative CSP for API-only app
        resp.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return resp

    if app.config.get('START_RETENTION_WORKER'):
        t = threading.Thread(target=_retention_worker, args=(app,))
        t.daemon = True
        t.start()

    return app


def _retention_worker(app: Flask):
    interval = int(os.getenv('RETENTION_SWEEP_SECONDS', '3600'))
    while True:
        try:
            with app.app_context():
                run_retention_once()
        except Exception:
            # Intentionally avoid verbose logging to minimize data exposure
            pass
        time.sleep(interval)


app = create_app()


if __name__ == '__main__':
    # Development server only. In production, use a WSGI server.
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))\



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/session', methods=['POST'])
def _auto_stub_session():
    return 'Auto-generated stub for /session', 200
