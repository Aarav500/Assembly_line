import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from config import Config
from db import db
from routes import api


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        from models import Model, Tag, ModelVersion, MetadataRevision, Artifact, Dataset, LineageEdge  # noqa: F401
        db.create_all()

    app.register_blueprint(api, url_prefix='/api')

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        response = e.get_response()
        response.data = app.json.dumps({
            'error': e.name,
            'message': e.description,
            'status': e.code,
        })
        response.content_type = 'application/json'
        return response

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8000, debug=True)



@app.route('/models', methods=['POST'])
def _auto_stub_models():
    return 'Auto-generated stub for /models', 200


@app.route('/models/test_model/v1', methods=['GET'])
def _auto_stub_models_test_model_v1():
    return 'Auto-generated stub for /models/test_model/v1', 200


@app.route('/lineage/child_model/v1', methods=['GET'])
def _auto_stub_lineage_child_model_v1():
    return 'Auto-generated stub for /lineage/child_model/v1', 200


@app.route('/lineage/parent_model/v1', methods=['GET'])
def _auto_stub_lineage_parent_model_v1():
    return 'Auto-generated stub for /lineage/parent_model/v1', 200


@app.route('/models/my_model', methods=['GET'])
def _auto_stub_models_my_model():
    return 'Auto-generated stub for /models/my_model', 200
