import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from config import Config
from models import db
from routes.api import api_bp
from tasks.runner import TaskRunner


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure DB and directories
    os.makedirs(os.path.dirname(app.config['DB_PATH']), exist_ok=True)
    db.init_db(app.config['DB_PATH'])

    # Attach a global task runner
    app.task_runner = TaskRunner()
    app.task_runner.start()

    # Register blueprints
    app.register_blueprint(api_bp)

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            'status': 'ok',
            'service': 'incident-response-automation',
            'version': '1.0.0'
        })

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))



@app.route('/incidents', methods=['POST'])
def _auto_stub_incidents():
    return 'Auto-generated stub for /incidents', 200
