import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Policy, Approval


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///governance_portal.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_if_empty()

    register_routes(app)
    return app


def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login', next=request.path))
            if role is not None:
                user = User.query.get(session['user_id'])
                if user is None or (isinstance(role, (list, tuple, set)) and user.role not in role) or (isinstance(role, str) and user.role != role):
                    flash('Not authorized.', 'error')
                    return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def seed_if_empty():
    if User.query.count() == 0:
        admin = User(username='admin', role='admin')
        admin.password_hash = generate_password_hash('admin123')
        reviewer = User(username='reviewer', role='reviewer')
        reviewer.password_hash = generate_password_hash('reviewer123')
        viewer = User(username='viewer', role='viewer')
        viewer.password_hash = generate_password_hash('viewer123')
        db.session.add_all([admin, reviewer, viewer])
        db.session.commit()

    if Policy.query.count() == 0:
        admin = User.query.filter_by(username='admin').first()
        reviewer = User.query.filter_by(username='reviewer').first()
        p1 = Policy(title='Information Security Policy', content='Defines security controls and responsibilities.', status='In Review', owner_id=admin.id, category='Security', version=1)
        p2 = Policy(title='Data Retention Policy', content='Specifies how long data is retained.', status='Draft', owner_id=admin.id, category='Compliance', version=1)
        p3 = Policy(title='Remote Work Policy', content='Guidelines for remote work.', status='Approved', owner_id=admin.id, category='HR', version=2)
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        # create approvals for p1 pending for reviewer
        a1 = Approval(policy_id=p1.id, approver_id=reviewer.id, status='Pending', created_at=datetime.datetime.utcnow())
        # add approval history for p3 as approved
        a2 = Approval(policy_id=p3.id, approver_id=reviewer.id, status='Approved', comment='Looks good', created_at=datetime.datetime.utcnow() - datetime.timedelta(days=7), decided_at=datetime.datetime.utcnow() - datetime.timedelta(days=7))
        db.session.add_all([a1, a2])
        db.session.commit()


def register_routes(app):
    # Placeholder for route registration
    pass


@app.route('/policies', methods=['GET', 'POST'])
def _auto_stub_policies():
    return 'Auto-generated stub for /policies', 200


@app.route('/metrics', methods=['GET'])
def _auto_stub_metrics():
    return 'Auto-generated stub for /metrics', 200


@app.route('/approvals', methods=['GET'])
def _auto_stub_approvals():
    return 'Auto-generated stub for /approvals', 200


if __name__ == '__main__':
    pass
