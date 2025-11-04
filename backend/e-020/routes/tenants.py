from flask import Blueprint, request, jsonify
from database import db
from models import Tenant

tenants_bp = Blueprint('tenants', __name__)


@tenants_bp.route('/tenants', methods=['POST'])
def create_tenant():
    data = request.get_json(force=True) or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name is required'}), 400
    t = Tenant(name=name)
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@tenants_bp.route('/tenants', methods=['GET'])
def list_tenants():
    items = Tenant.query.order_by(Tenant.id.asc()).all()
    return jsonify([t.to_dict() for t in items])


@tenants_bp.route('/tenants/<int:tenant_id>', methods=['GET'])
def get_tenant(tenant_id):
    t = Tenant.query.get_or_404(tenant_id)
    return jsonify(t.to_dict())

