import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from config import Config
from models import db
from auth import bp as auth_bp
from datasets import bp as datasets_bp
from audit import bp as audit_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    app.register_blueprint(auth_bp)
    app.register_blueprint(datasets_bp)
    app.register_blueprint(audit_bp)

    @app.get("/")
    def index():
        return jsonify({"status": "ok", "message": "Access Controls and Auditing API"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)



@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200


@app.route('/datasets', methods=['GET'])
def _auto_stub_datasets():
    return 'Auto-generated stub for /datasets', 200


@app.route('/datasets/customer_data', methods=['GET'])
def _auto_stub_datasets_customer_data():
    return 'Auto-generated stub for /datasets/customer_data', 200


@app.route('/datasets/sales_data', methods=['GET'])
def _auto_stub_datasets_sales_data():
    return 'Auto-generated stub for /datasets/sales_data', 200


@app.route('/audit', methods=['GET'])
def _auto_stub_audit():
    return 'Auto-generated stub for /audit', 200
