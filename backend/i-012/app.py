import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, g, redirect, url_for, session
from config import Config
from models import db, User
from auth import auth_bp
from views import main_bp
from approval import approvals_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(approvals_bp)

    @app.before_request
    def load_user():
        user_id = session.get('user_id')
        g.user = None
        if user_id:
            g.user = User.query.get(user_id)

    @app.route('/')
    def index():
        if not g.user:
            return redirect(url_for('auth.login'))
        return redirect(url_for('main.dashboard'))

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)



@app.route('/login', methods=['POST'])
def _auto_stub_login():
    return 'Auto-generated stub for /login', 200


@app.route('/dashboard', methods=['GET'])
def _auto_stub_dashboard():
    return 'Auto-generated stub for /dashboard', 200


@app.route('/api/permissions/project1', methods=['GET'])
def _auto_stub_api_permissions_project1():
    return 'Auto-generated stub for /api/permissions/project1', 200


@app.route('/request-access', methods=['POST'])
def _auto_stub_request_access():
    return 'Auto-generated stub for /request-access', 200
