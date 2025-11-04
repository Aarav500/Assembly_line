from flask import jsonify
from models import LineageEdge, ModelVersion, Dataset
from . import api

@api.route('/lineage/model-versions/<int:version_id>', methods=['GET'])
def get_lineage_for_model_version(version_id):
    mv = ModelVersion.query.get_or_404(version_id)
    parents = LineageEdge.query.filter_by(child_type='model_version', child_id=mv.id).all()
    children = LineageEdge.query.filter_by(parent_type='model_version', parent_id=mv.id).all()

    def resolve_node(node_type, node_id):
        if node_type == 'model_version':
            mv2 = ModelVersion.query.get(node_id)
            if not mv2:
                return None
            return {
                'type': 'model_version',
                'id': mv2.id,
                'model_id': mv2.model_id,
                'version': mv2.version,
                'stage': mv2.stage,
            }
        elif node_type == 'dataset':
            ds = Dataset.query.get(node_id)
            if not ds:
                return None
            return {
                'type': 'dataset',
                'id': ds.id,
                'name': ds.name,
                'uri': ds.uri,
            }
        return None

    return jsonify({
        'model_version': {
            'id': mv.id,
            'model_id': mv.model_id,
            'version': mv.version,
            'stage': mv.stage,
        },
        'parents': [
            {
                'edge': e.to_dict(),
                'node': resolve_node(e.parent_type, e.parent_id),
            } for e in parents
        ],
        'children': [
            {
                'edge': e.to_dict(),
                'node': resolve_node(e.child_type, e.child_id),
            } for e in children
        ]
    })

