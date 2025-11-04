import os
from flask import Blueprint, jsonify
from models import Run

audit_bp = Blueprint('audit', __name__)


@audit_bp.get('/lineage/<int:run_id>')
def lineage(run_id: int):
    run = Run.query.get_or_404(run_id)
    # Build a simple lineage graph structure
    nodes = []
    edges = []

    run_node_id = f'run:{run.id}'
    nodes.append({'id': run_node_id, 'type': 'run', 'data': {'id': run.id, 'name': run.name}})

    if run.code_version:
        code_node_id = f'code:{run.code_version.id}'
        nodes.append({'id': code_node_id, 'type': 'code_version', 'data': run.code_version.to_dict()})
        edges.append({'from': code_node_id, 'to': run_node_id, 'relation': 'used_by'})

    if run.environment:
        env_node_id = f'env:{run.environment.id}'
        nodes.append({'id': env_node_id, 'type': 'environment', 'data': run.environment.to_dict()})
        edges.append({'from': env_node_id, 'to': run_node_id, 'relation': 'used_by'})

    for rd in run.datasets:
        ds_node_id = f'ds:{rd.dataset.id}'
        nodes.append({'id': ds_node_id, 'type': 'dataset', 'data': rd.dataset.to_dict()})
        edges.append({'from': ds_node_id, 'to': run_node_id, 'relation': rd.role})

    for a in run.artifacts:
        art_node_id = f'art:{a.id}'
        nodes.append({'id': art_node_id, 'type': 'artifact', 'data': a.to_dict()})
        edges.append({'from': run_node_id, 'to': art_node_id, 'relation': 'produces'})

    return jsonify({'nodes': nodes, 'edges': edges})


@audit_bp.get('/bundles/<int:run_id>')
def list_bundles(run_id: int):
    run = Run.query.get_or_404(run_id)
    return [b.to_dict() for b in run.bundles]

