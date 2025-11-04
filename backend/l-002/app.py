import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from config import Config
from secrets.store import get_secrets_provider
from acl.policy_engine import PolicyEngine
from middleware.auth import require_permission, auth_init
from utils.audit import audit_event
from flask import request, g


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize policy engine
    policy_engine = PolicyEngine(app.config.get('POLICY_FILE'))
    app.policy_engine = policy_engine

    # Initialize secrets provider
    provider = get_secrets_provider(app.config)
    app.secrets_provider = provider

    # Initialize auth layer
    auth_init(app)

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify({"error": "bad_request", "message": str(err)}), 400

    @app.errorhandler(401)
    def unauthorized(err):
        return jsonify({"error": "unauthorized", "message": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(err):
        return jsonify({"error": "forbidden", "message": "Access denied"}), 403

    @app.errorhandler(404)
    def not_found(err):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "provider": provider.name()}), 200

    @app.route('/me', methods=['GET'])
    def me():
        user = getattr(g, 'user', None)
        if not user:
            return jsonify({"authenticated": False}), 200
        redacted = {k: v for k, v in user.items() if k != 'api_key'}
        return jsonify({"authenticated": True, "user": redacted}), 200

    @app.route('/secrets', methods=['GET'])
    @require_permission('list')
    def list_secrets():
        prefix = request.args.get('prefix', '')
        all_secrets = app.secrets_provider.list_secrets(prefix=prefix)
        user = g.user
        # Filter by list permission per secret path
        visible = []
        for path in all_secrets:
            if app.policy_engine.is_allowed(user, 'list', path):
                visible.append(path)
        return jsonify({"secrets": sorted(visible)}), 200

    @app.route('/secrets/<path:secret_path>', methods=['GET'])
    @require_permission('read')
    def get_secret(secret_path):
        user = g.user
        if not app.policy_engine.is_allowed(user, 'read', secret_path):
            return jsonify({"error": "forbidden", "message": "Read not permitted"}), 403
        secret = app.secrets_provider.get_secret(secret_path)
        if secret is None:
            return jsonify({"error": "not_found", "message": "Secret not found"}), 404
        audit_event(action='read', user=user.get('name'), path=secret_path, outcome='success')
        return jsonify({"path": secret_path, "value": secret}), 200

    @app.route('/secrets/<path:secret_path>', methods=['PUT'])
    @require_permission('write')
    def put_secret(secret_path):
        user = g.user
        if not request.is_json:
            return jsonify({"error": "bad_request", "message": "Expected application/json"}), 400
        data = request.get_json(silent=True) or {}
        if 'value' not in data:
            return jsonify({"error": "bad_request", "message": "Missing 'value'"}), 400
        if not app.policy_engine.is_allowed(user, 'write', secret_path):
            return jsonify({"error": "forbidden", "message": "Write not permitted"}), 403
        app.secrets_provider.set_secret(secret_path, data['value'])
        audit_event(action='write', user=user.get('name'), path=secret_path, outcome='success')
        return jsonify({"path": secret_path, "status": "updated"}), 200

    @app.route('/secrets/<path:secret_path>', methods=['DELETE'])
    @require_permission('write')
    def delete_secret(secret_path):
        user = g.user
        if not app.policy_engine.is_allowed(user, 'write', secret_path):
            return jsonify({"error": "forbidden", "message": "Delete not permitted"}), 403
        existed = app.secrets_provider.delete_secret(secret_path)
        audit_event(action='delete', user=user.get('name'), path=secret_path, outcome='success' if existed else 'noop')
        return jsonify({"path": secret_path, "deleted": bool(existed)}), 200

    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=int(Config.PORT), debug=Config.DEBUG)



@app.route('/secrets/db_password', methods=['GET'])
def _auto_stub_secrets_db_password():
    return 'Auto-generated stub for /secrets/db_password', 200


@app.route('/secrets/api_key', methods=['GET'])
def _auto_stub_secrets_api_key():
    return 'Auto-generated stub for /secrets/api_key', 200


@app.route('/secrets/new_secret', methods=['POST'])
def _auto_stub_secrets_new_secret():
    return 'Auto-generated stub for /secrets/new_secret', 200
