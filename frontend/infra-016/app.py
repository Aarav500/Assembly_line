import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from flask import Flask, jsonify
from notification_service.config import get_settings
from notification_service.routes.notifications import bp as notifications_bp
from pydantic import ValidationError


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


def create_app() -> Flask:
    app = Flask(__name__)

    # Load settings at startup
    settings = get_settings()
    app.config['SETTINGS'] = settings

    # Blueprints
    app.register_blueprint(notifications_bp, url_prefix='/api')

    @app.get('/health')
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return jsonify({"error": "validation_error", "details": err.errors()}), 400

    @app.errorhandler(404)
    def handle_not_found(err):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(Exception)
    def handle_generic_error(err: Exception):
        logging.exception("Unhandled error")
        return jsonify({"error": "internal_server_error", "message": str(err)}), 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)



@app.route('/api/notifications/send', methods=['POST'])
def _auto_stub_api_notifications_send():
    return 'Auto-generated stub for /api/notifications/send', 200
