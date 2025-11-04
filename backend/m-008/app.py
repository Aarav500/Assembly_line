import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from config import Config
from models import db
from routes import bp as routes_bp


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(routes_bp)

    @app.route('/health')
    def health():
        return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat() + 'Z'}

    # Register CLI command
    from todo_extractor import scan_and_update_backlog

    @app.cli.command('scan')
    def scan_command():
        """Scan the repository for TODOs and update backlog items."""
        result = scan_and_update_backlog(app)
        print(f"Scan complete: new={result['new']}, updated={result['updated']}, resolved={result['resolved']}, open={result['open']}")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/extract', methods=['POST'])
def _auto_stub_extract():
    return 'Auto-generated stub for /extract', 200
