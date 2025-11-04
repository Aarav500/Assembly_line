import os
from flask import Blueprint, request, jsonify, current_app, make_response, abort

from versioning import router
from services import items_service

api_bp = Blueprint('api', __name__)


# Register versioned handlers
# Items list (GET)
router.register('items_list', '2.0', items_service.list_items_v2)
router.register('items_list', '1.0', items_service.list_items_v1)
router.register('items_list', '1.1', items_service.list_items_v1)  # same as 1.0 for demo

# Items create (POST) - only v2 implemented; v1 will be adapted
router.register('items_create', '2.0', items_service.create_item_v2)


@api_bp.route('/api/items', methods=['GET'], defaults={'path_version': None})
@api_bp.route('/api/v<path:path_version>/items', methods=['GET'])
def get_items(path_version):
    return router.dispatch('items_list', request, method='GET', path_version=path_version, resource_name='items')


@api_bp.route('/api/items', methods=['POST'], defaults={'path_version': None})
@api_bp.route('/api/v<path:path_version>/items', methods=['POST'])
def create_item(path_version):
    return router.dispatch('items_create', request, method='POST', path_version=path_version, resource_name='items')


@api_bp.route('/api/versions', methods=['GET'])
def versions_info():
    cfg = current_app.config
    return {
        'supported_versions': cfg['SUPPORTED_VERSIONS'],
        'latest_version': cfg['LATEST_VERSION'],
        'deprecated': list(cfg.get('DEPRECATED_VERSIONS', {}).keys()),
    }


@api_bp.route('/api/migrations', methods=['GET'])
def list_migrations():
    base_path = os.path.join(current_app.root_path, 'docs', 'migrations')
    try:
        files = sorted([f for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))])
    except FileNotFoundError:
        files = []
    base_url = current_app.config.get('MIGRATIONS_BASE_URL', '')
    guides = []
    for f in files:
        guides.append({
            'file': f,
            'path': f'/api/migrations/{f}',
            'external': f'{base_url}/{f}' if base_url else None
        })
    return {'guides': guides}


@api_bp.route('/api/migrations/<path:filename>', methods=['GET'])
def get_migration(filename):
    # Very basic safe file read
    safe_name = os.path.basename(filename)
    base_path = os.path.join(current_app.root_path, 'docs', 'migrations')
    file_path = os.path.join(base_path, safe_name)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        abort(404)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    resp = make_response(content, 200)
    resp.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return resp

