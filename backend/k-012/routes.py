from typing import Any, Dict
from flask import Blueprint, request, jsonify
from models import db
from repositories import OrganizationRepository, AgentRepository, ResourceRepository
from security import org_required
from tenant import current_tenant
from agents.manager import AgentManager


api = Blueprint('api', __name__, url_prefix='/api')


@api.errorhandler(404)
def not_found(e):
    return jsonify({"error": {"code": "not_found", "message": "Resource not found"}}), 404


@api.route('/orgs', methods=['POST'])
def create_org():
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    if not name:
        return jsonify({"error": {"code": "invalid_input", "message": "name is required"}}), 400
    try:
        org = OrganizationRepository.create(name)
        return jsonify({
            "data": {
                "id": org.id,
                "name": org.name,
                "api_key": org.api_key,
            }
        }), 201
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": {"code": "conflict", "message": str(ex)}}), 409


@api.route('/agents', methods=['POST'])
@org_required
def create_agent():
    tenant = current_tenant()
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    type_ = (payload.get('type') or '').strip()
    config = payload.get('config') or {}
    if not name or not type_:
        return jsonify({"error": {"code": "invalid_input", "message": "name and type are required"}}), 400
    try:
        agent = AgentRepository.create(tenant.org, name=name, type=type_, config=config)
        return jsonify({"data": {"id": agent.id, "name": agent.name, "type": agent.type}}), 201
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": {"code": "conflict", "message": str(ex)}}), 409


@api.route('/agents', methods=['GET'])
@org_required
def list_agents():
    tenant = current_tenant()
    agents = AgentRepository.list_for_org(tenant.org)
    return jsonify({"data": [{"id": a.id, "name": a.name, "type": a.type} for a in agents]})


@api.route('/resources', methods=['POST'])
@org_required
def create_resource():
    tenant = current_tenant()
    payload = request.get_json(silent=True) or {}
    title = (payload.get('title') or '').strip()
    content = (payload.get('content') or '').strip()
    if not title or not content:
        return jsonify({"error": {"code": "invalid_input", "message": "title and content are required"}}), 400
    try:
        resource = ResourceRepository.create(tenant.org, title=title, content=content)
        # Invalidate cache potentially used by agents
        tenant.cache_delete('agents:echo:list_resources')
        return jsonify({"data": {"id": resource.id, "title": resource.title}}), 201
    except Exception as ex:
        db.session.rollback()
        return jsonify({"error": {"code": "conflict", "message": str(ex)}}), 409


@api.route('/resources', methods=['GET'])
@org_required
def list_resources():
    tenant = current_tenant()
    cache_key = 'resource_list:v1'
    cached = tenant.cache_get(cache_key)
    if cached is not None:
        return jsonify({"data": cached, "cached": True})
    items = ResourceRepository.list_for_org(tenant.org)
    data = [{"id": r.id, "title": r.title, "created_at": r.created_at.isoformat()} for r in items]
    tenant.cache_set(cache_key, data, ttl_seconds=10)
    return jsonify({"data": data, "cached": False})


@api.route('/agents/<int:agent_id>/actions/<string:action>', methods=['POST'])
@org_required
def run_agent_action(agent_id: int, action: str):
    tenant = current_tenant()
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    manager = AgentManager(org=tenant.org)
    result = manager.run(agent_id, action, payload, tenant)
    status = 200 if 'error' not in result else (404 if result['error']['code'] in ('not_found',) else 400)
    return jsonify(result), status


