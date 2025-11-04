from flask import Blueprint, request, jsonify
from sqlalchemy import and_, func
from database import db
from models import Tenant, Project, Resource, ResourceTag
from utils.tags import upsert_tags, parse_tag_filters

resources_bp = Blueprint('resources', __name__)


@resources_bp.route('/projects/<int:project_id>/resources', methods=['POST'])
def create_resource(project_id):
    p = Project.query.get_or_404(project_id)
    data = request.get_json(force=True) or {}
    name = data.get('name')
    rtype = data.get('type')
    size = data.get('size')
    base_rate = data.get('base_rate')
    tags = data.get('tags') or {}

    if not name or not rtype:
        return jsonify({'error': 'name and type are required'}), 400

    r = Resource(
        name=name,
        type=str(rtype).lower(),
        size=size,
        base_rate=base_rate,
        tenant_id=p.tenant_id,
        project_id=p.id,
        active=True,
    )
    db.session.add(r)
    db.session.flush()
    if tags:
        upsert_tags(r, tags)
    db.session.commit()
    return jsonify(r.to_dict()), 201


@resources_bp.route('/resources/<int:resource_id>', methods=['GET'])
def get_resource(resource_id):
    r = Resource.query.get_or_404(resource_id)
    return jsonify(r.to_dict())


@resources_bp.route('/resources', methods=['GET'])
def list_resources():
    tenant_id = request.args.get('tenant_id', type=int)
    project_id = request.args.get('project_id', type=int)
    active = request.args.get('active')
    tag_filters = parse_tag_filters(request.args)

    q = Resource.query
    if tenant_id:
        q = q.filter(Resource.tenant_id == tenant_id)
    if project_id:
        q = q.filter(Resource.project_id == project_id)
    if active is not None:
        if active.lower() in ('true', '1', 'yes'):
            q = q.filter(Resource.active.is_(True))
        elif active.lower() in ('false', '0', 'no'):
            q = q.filter(Resource.active.is_(False))
    # Tag filtering: all provided tags must match
    for k, v in tag_filters.items():
        alias = ResourceTag
        q = q.join(alias, and_(alias.resource_id == Resource.id, alias.key == str(k), alias.value == str(v)))

    q = q.order_by(Resource.id.asc())
    items = q.all()
    return jsonify([r.to_dict() for r in items])


@resources_bp.route('/resources/<int:resource_id>/tags', methods=['PUT', 'PATCH'])
def update_tags(resource_id):
    r = Resource.query.get_or_404(resource_id)
    data = request.get_json(force=True) or {}
    tags = data.get('tags') or {}
    upsert_tags(r, tags)
    db.session.commit()
    return jsonify(r.to_dict())


@resources_bp.route('/resources/<int:resource_id>', methods=['PATCH'])
def patch_resource(resource_id):
    r = Resource.query.get_or_404(resource_id)
    data = request.get_json(force=True) or {}
    changed = False
    if 'name' in data:
        r.name = data['name']
        changed = True
    if 'size' in data:
        r.size = data['size']
        changed = True
    if 'base_rate' in data:
        r.base_rate = data['base_rate']
        changed = True
    if 'active' in data:
        r.active = bool(data['active'])
        changed = True
    if 'tags' in data:
        upsert_tags(r, data.get('tags') or {})
        changed = True
    if changed:
        db.session.commit()
    return jsonify(r.to_dict())

