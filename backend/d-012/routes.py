from flask import Blueprint, request, jsonify
from models import get_session
from services.registry import ServiceRegistry
from services.monitor import Monitor
from services.incident import IncidentManager
from services.deployer import Deployer
from services.log_buffer import LogBuffer

api_bp = Blueprint('api', __name__)

# Initialize singletons
session_factory = get_session
registry = ServiceRegistry(session_factory)
monitor = Monitor()
incident_manager = IncidentManager(session_factory)
log_buffer = LogBuffer(capacity_per_service=500)

deployer = Deployer(registry=registry, monitor=monitor, incident_manager=incident_manager, log_buffer=log_buffer)


@api_bp.post('/deploy')
def deploy():
    data = request.get_json(force=True, silent=True) or {}
    service = data.get('service')
    version = data.get('version')
    if not service or not version:
        return jsonify({'error': 'service and version are required'}), 400
    try:
        result = deployer.deploy(service, version)
        return jsonify(result)
    except Exception as e:
        log_buffer.add(service or 'unknown', 'ERROR', 'Deployment exception', error=str(e))
        return jsonify({'error': str(e)}), 500


@api_bp.get('/services')
def list_services():
    return jsonify({'services': registry.list_states()})


@api_bp.post('/simulate/failure')
def simulate_failure():
    data = request.get_json(force=True, silent=True) or {}
    service = data.get('service')
    version = data.get('version')
    reason = data.get('reason', 'simulated_failure')
    error_code = data.get('error_code')
    if not service or not version:
        return jsonify({'error': 'service and version are required'}), 400
    monitor.inject_failure(service, version, {'reason': reason, 'error_code': error_code})
    log_buffer.add(service, 'WARN', 'Injected failure for version', version=version, reason=reason)
    return jsonify({'status': 'injected', 'service': service, 'version': version, 'reason': reason})


@api_bp.post('/simulate/failure/clear')
def clear_failure():
    data = request.get_json(force=True, silent=True) or {}
    service = data.get('service')
    version = data.get('version')
    if not service or not version:
        return jsonify({'error': 'service and version are required'}), 400
    monitor.clear_failure(service, version)
    log_buffer.add(service, 'INFO', 'Cleared failure injection', version=version)
    return jsonify({'status': 'cleared', 'service': service, 'version': version})


@api_bp.get('/incidents')
def list_incidents():
    return jsonify({'incidents': incident_manager.list_incidents()})


@api_bp.get('/incidents/<int:incident_id>')
def get_incident(incident_id: int):
    inc = incident_manager.get_incident(incident_id)
    if not inc:
        return jsonify({'error': 'not_found'}), 404
    return jsonify(inc)


@api_bp.post('/incidents/<int:incident_id>/resolve')
def resolve_incident(incident_id: int):
    ok = incident_manager.resolve_incident(incident_id)
    if not ok:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({'status': 'resolved', 'id': incident_id})


@api_bp.get('/logs/<service>')
def get_logs(service: str):
    n = request.args.get('n', default=50, type=int)
    return jsonify({'service': service, 'logs': log_buffer.tail(service, n)})

