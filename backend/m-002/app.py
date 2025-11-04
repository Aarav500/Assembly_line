import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify, render_template, abort, current_app
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException

from config import BaseConfig
from models import db, User, Product, Order, OrderItem
from seeders.demo_data import generate_demo_data, get_counts, clear_database

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(BaseConfig)

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    register_error_handlers(app)

    return app


def ensure_allowed():
    cfg = current_app.config
    if not (cfg.get('APP_ENV') == 'staging' or cfg.get('ALLOW_DEMO_DATA')):
        abort(403, description='Demo data is allowed only in staging environments. Set APP_ENV=staging or ALLOW_DEMO_DATA=true to override.')


def require_token_if_configured():
    cfg = current_app.config
    required = cfg.get('DEMO_DATA_TOKEN')
    if required:
        sent = request.headers.get('X-Auth-Token')
        if not sent and request.is_json:
            sent = (request.get_json(silent=True) or {}).get('token')
        if not sent:
            sent = request.args.get('token')
        if not sent or sent != required:
            abort(401, description='Invalid or missing auth token')


def register_routes(app: Flask):
    @app.get('/')
    def home():
        return jsonify({
            'message': 'Demo Data Generator running',
            'admin': '/admin/demo-data'
        })

    @app.get('/admin/demo-data')
    def admin_page():
        ensure_allowed()
        token_required = bool(current_app.config.get('DEMO_DATA_TOKEN'))
        return render_template('demo/index.html',
                               env=current_app.config.get('APP_ENV', 'development'),
                               token_required=token_required)

    @app.get('/admin/demo-data/status')
    def status():
        ensure_allowed()
        require_token_if_configured()
        counts = get_counts()
        return jsonify({
            'environment': current_app.config.get('APP_ENV'),
            'counts': counts
        })

    @app.post('/admin/demo-data/generate')
    def demo_generate():
        ensure_allowed()
        require_token_if_configured()
        payload = request.get_json(silent=True) or {}
        reset = bool(payload.get('reset', False))
        seed = payload.get('seed')
        try:
            users = int(payload.get('users', 25))
            products = int(payload.get('products', 20))
            orders = int(payload.get('orders', 50))
        except Exception:
            abort(400, description='Invalid numeric parameters')

        if users < 0 or products < 0 or orders < 0:
            abort(400, description='Counts must be non-negative integers')

        with current_app.app_context():
            if reset:
                clear_database()
                db.session.commit()

            result = generate_demo_data(target_users=users, target_products=products, target_orders=orders, seed=seed)
            db.session.commit()

        return jsonify({
            'ok': True,
            'message': 'Demo data generated',
            'created': result['created'],
            'totals': result['totals']
        })


def register_error_handlers(app: Flask):
    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        response = jsonify({
            'ok': False,
            'error': e.name,
            'status': e.code,
            'message': e.description,
        })
        return response, e.code

    @app.errorhandler(Exception)
    def handle_exception(e: Exception):
        response = jsonify({
            'ok': False,
            'error': 'Internal Server Error',
            'status': 500,
            'message': str(e),
        })
        return response, 500


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



@app.route('/data', methods=['GET'])
def _auto_stub_data():
    return 'Auto-generated stub for /data', 200


@app.route('/reset', methods=['POST'])
def _auto_stub_reset():
    return 'Auto-generated stub for /reset', 200
