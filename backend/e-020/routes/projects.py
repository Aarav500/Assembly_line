from flask import Blueprint, request, jsonify
from database import db
from models import Tenant, Project

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/tenants/<int:tenant_id>/projects', methods=['POST'])
def create_project(tenant_id):
    Tenant.query.get_or_404(tenant_id)
    data = request.get_json(force=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    p = Project(name=name, tenant_id=tenant_id)
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@projects_bp.route('/tenants/<int:tenant_id>/projects', methods=['GET'])
def list_projects(tenant_id):
    Tenant.query.get_or_404(tenant_id)
    items = Project.query.filter_by(tenant_id=tenant_id).order_by(Project.id.asc()).all()
    return jsonify([p.to_dict() for p in items])


@projects_bp.route('/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    p = Project.query.get_or_404(project_id)
    return jsonify(p.to_dict())

