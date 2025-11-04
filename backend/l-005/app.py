import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
from config import Config
from models import db, User
from auth import auth_bp
from marketplace import marketplace_bp
from payments import payments_bp

load_dotenv()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(payments_bp)

    @app.cli.command('db-create')
    def db_create():
        with app.app_context():
            db.create_all()
            print('Database tables created.')

    @app.cli.command('create-user')
    def create_user():
        """Interactive user creation."""
        with app.app_context():
            email = input('Email: ').strip().lower()
            if not email:
                print('Email required')
                return
            if User.query.filter_by(email=email).first():
                print('User already exists')
                return
            password = input('Password: ').strip()
            is_seller = input('Is seller? [y/N]: ').strip().lower() == 'y'
            user = User(email=email, is_seller=is_seller)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            print('User created.')

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)



@app.route('/templates', methods=['POST'])
def _auto_stub_templates():
    return 'Auto-generated stub for /templates', 200


@app.route('/blueprints', methods=['POST'])
def _auto_stub_blueprints():
    return 'Auto-generated stub for /blueprints', 200


@app.route('/purchase', methods=['POST'])
def _auto_stub_purchase():
    return 'Auto-generated stub for /purchase', 200


@app.route('/purchases/user123', methods=['GET'])
def _auto_stub_purchases_user123():
    return 'Auto-generated stub for /purchases/user123', 200
