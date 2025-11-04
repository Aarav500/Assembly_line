from flask import Blueprint, request
from db import db
from models import Environment

env_bp = Blueprint('environments', __name__)


@env_bp.post('')
def create_environment():
    data = request.get_json(force=True)
    env = Environment(
        python_version=data.get('python_version'),
        pip_freeze=data.get('pip_freeze'),
        docker_image=data.get('docker_image'),
        conda_env=data.get('conda_env'),
        os_info=data.get('os_info'),
    )
    db.session.add(env)
    db.session.commit()
    return env.to_dict(), 201


@env_bp.get('')
def list_environments():
    q = Environment.query.order_by(Environment.created_at.desc()).all()
    return [e.to_dict() for e in q]


@env_bp.get('/<int:env_id>')
def get_environment(env_id: int):
    e = Environment.query.get_or_404(env_id)
    return e.to_dict()

