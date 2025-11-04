import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import yaml
import os

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/generate', methods=['POST'])
def generate_operator():
    data = request.get_json()
    
    if not data or 'name' not in data or 'group' not in data or 'version' not in data:
        return jsonify({'error': 'Missing required fields: name, group, version'}), 400
    
    operator_name = data['name']
    group = data['group']
    version = data['version']
    kind = data.get('kind', operator_name.capitalize())
    
    crd = generate_crd(operator_name, group, version, kind)
    controller = generate_controller(operator_name, group, version, kind)
    dockerfile = generate_dockerfile()
    
    return jsonify({
        'operator_name': operator_name,
        'files': {
            'crd.yaml': crd,
            'controller.py': controller,
            'Dockerfile': dockerfile
        }
    }), 200

def generate_crd(name, group, version, kind):
    crd = {
        'apiVersion': 'apiextensions.k8s.io/v1',
        'kind': 'CustomResourceDefinition',
        'metadata': {
            'name': f"{name}s.{group}"
        },
        'spec': {
            'group': group,
            'versions': [{
                'name': version,
                'served': True,
                'storage': True,
                'schema': {
                    'openAPIV3Schema': {
                        'type': 'object',
                        'properties': {
                            'spec': {
                                'type': 'object',
                                'properties': {
                                    'replicas': {'type': 'integer'},
                                    'image': {'type': 'string'}
                                }
                            },
                            'status': {
                                'type': 'object',
                                'properties': {
                                    'state': {'type': 'string'}
                                }
                            }
                        }
                    }
                }
            }],
            'scope': 'Namespaced',
            'names': {
                'plural': f"{name}s",
                'singular': name,
                'kind': kind,
                'shortNames': [name[:3]]
            }
        }
    }
    return yaml.dump(crd, default_flow_style=False)

def generate_controller(name, group, version, kind):
    controller = f'''import kopf
import kubernetes

@kopf.on.create('{group}', '{version}', '{name}s')
def create_fn(spec, name, namespace, logger, **kwargs):
    logger.info(f"Creating {{name}} in namespace {{namespace}}")
    replicas = spec.get('replicas', 1)
    image = spec.get('image', 'nginx:latest')
    
    # Add your operator logic here
    logger.info(f"Replicas: {{replicas}}, Image: {{image}}")
    
    return {{'message': f'{{name}} created successfully'}}

@kopf.on.update('{group}', '{version}', '{name}s')
def update_fn(spec, name, namespace, logger, **kwargs):
    logger.info(f"Updating {{name}} in namespace {{namespace}}")
    return {{'message': f'{{name}} updated successfully'}}

@kopf.on.delete('{group}', '{version}', '{name}s')
def delete_fn(spec, name, namespace, logger, **kwargs):
    logger.info(f"Deleting {{name}} in namespace {{namespace}}")
    return {{'message': f'{{name}} deleted successfully'}}
'''
    return controller

def generate_dockerfile():
    dockerfile = '''FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY controller.py .

CMD ["kopf", "run", "controller.py", "--verbose"]
'''
    return dockerfile

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
