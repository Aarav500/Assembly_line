import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import yaml
import base64
from threading import Lock

app = Flask(__name__)

vm_templates = {}
template_lock = Lock()

@app.route('/', methods=['GET'])
def index():
    return jsonify({"service": "VM Provisioning with Cloud-Init", "status": "running"})

@app.route('/cloud-init/generate', methods=['POST'])
def generate_cloud_init():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        hostname = data.get('hostname', 'vm-instance')
        users = data.get('users', [])
        packages = data.get('packages', [])
        runcmd = data.get('runcmd', [])

        cloud_init_config = {
            'hostname': hostname,
            'manage_etc_hosts': True,
            'users': users,
            'packages': packages,
            'runcmd': runcmd
        }

        yaml_content = yaml.dump(cloud_init_config, default_flow_style=False)
        userdata = f"#cloud-config\n{yaml_content}"

        return jsonify({
            'cloud_init': userdata,
            'encoded': base64.b64encode(userdata.encode()).decode()
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/templates', methods=['GET'])
def list_templates():
    with template_lock:
        return jsonify({'templates': list(vm_templates.keys())})

@app.route('/templates/<name>', methods=['POST'])
def create_template(name):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        with template_lock:
            vm_templates[name] = data
        return jsonify({'message': f'Template {name} created', 'template': data}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/templates/<name>', methods=['GET'])
def get_template(name):
    with template_lock:
        if name not in vm_templates:
            return jsonify({'error': 'Template not found'}), 404
        return jsonify(vm_templates[name])

if __name__ == '__main__':
    import os
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)


def create_app():
    return app


@app.route('/templates/web', methods=['GET', 'POST'])
def _auto_stub_templates_web():
    return 'Auto-generated stub for /templates/web', 200
