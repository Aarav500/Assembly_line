import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import io
import json
from flask import Flask, jsonify, request, send_file
from service.template_manager import TemplateManager, TemplateNotFound, InvalidRequest


def create_app():
    app = Flask(__name__)
    manager = TemplateManager(
        templates_root=os.path.join(os.path.dirname(__file__), 'infra_templates'),
        metadata_path=os.path.join(os.path.dirname(__file__), 'templates_data', 'metadata.json')
    )

    @app.get('/')
    def root():
        return jsonify({
            'name': 'Infra Template Marketplace',
            'version': '1.0.0',
            'endpoints': {
                'list': '/api/templates',
                'detail': '/api/templates/<key>',
                'generate': '/api/generate'
            }
        })

    @app.get('/api/templates')
    def list_templates():
        templates = manager.list_templates()
        return jsonify({'templates': templates})

    @app.get('/api/templates/<key>')
    def get_template(key):
        try:
            t = manager.get_template(key)
            return jsonify(t)
        except TemplateNotFound as e:
            return jsonify({'error': str(e)}), 404

    @app.post('/api/generate')
    def generate():
        try:
            payload = request.get_json(force=True, silent=False) or {}
            key = payload.get('template')
            include = payload.get('include')  # list of components to include (e.g., ['docker-compose','k8s','terraform'])
            params = payload.get('params', {})
            output_format = (payload.get('format') or 'json').lower()

            files = manager.render_template(key, params=params, include=include)

            if output_format == 'zip':
                import zipfile
                mem = io.BytesIO()
                with zipfile.ZipFile(mem, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
                    for path, content in files.items():
                        zf.writestr(path, content)
                mem.seek(0)
                fname = f"{key or 'template'}-bundle.zip"
                return send_file(mem, mimetype='application/zip', as_attachment=True, download_name=fname)

            # default json
            return jsonify({'files': files})
        except (TemplateNotFound, InvalidRequest) as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': 'Internal server error', 'detail': str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)



@app.route('/templates/1', methods=['GET'])
def _auto_stub_templates_1():
    return 'Auto-generated stub for /templates/1', 200


@app.route('/templates/999', methods=['GET'])
def _auto_stub_templates_999():
    return 'Auto-generated stub for /templates/999', 200


@app.route('/templates/category/ecommerce', methods=['GET'])
def _auto_stub_templates_category_ecommerce():
    return 'Auto-generated stub for /templates/category/ecommerce', 200
