import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Helm Chart Generator Service', 'status': 'running'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/generate-chart', methods=['POST'])
def generate_chart():
    data = request.get_json()
    if not data or 'service_name' not in data:
        return jsonify({'error': 'service_name is required'}), 400
    
    service_name = data['service_name']
    namespace = data.get('namespace', 'default')
    replicas = data.get('replicas', 1)
    
    chart_template = {
        'apiVersion': 'v2',
        'name': service_name,
        'version': '0.1.0',
        'deployment': {
            'replicas': replicas,
            'namespace': namespace
        }
    }
    
    return jsonify({'chart': chart_template, 'message': 'Chart generated successfully'}), 201

@app.route('/template', methods=['POST'])
def render_template():
    data = request.get_json()
    if not data or 'values' not in data:
        return jsonify({'error': 'values are required'}), 400
    
    values = data['values']
    service_name = values.get('name', 'microservice')
    
    rendered = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
spec:
  replicas: {values.get('replicas', 1)}
  selector:
    matchLabels:
      app: {service_name}"""
    
    return jsonify({'rendered': rendered}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
