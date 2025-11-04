import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import json
import os
from datetime import datetime

app = Flask(__name__)

DOMAINS_FILE = 'domains.json'
CERTS_FILE = 'certificates.json'

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    return jsonify({'message': 'DNS & Domain Provisioning Automation with ACME Certs'})

@app.route('/domains', methods=['GET', 'POST'])
def domains():
    domains_data = load_data(DOMAINS_FILE)
    
    if request.method == 'POST':
        data = request.get_json()
        domain_name = data.get('domain')
        dns_records = data.get('dns_records', [])
        
        if not domain_name:
            return jsonify({'error': 'Domain name is required'}), 400
        
        domains_data[domain_name] = {
            'dns_records': dns_records,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
        save_data(DOMAINS_FILE, domains_data)
        return jsonify({'message': 'Domain provisioned', 'domain': domain_name}), 201
    
    return jsonify(domains_data)

@app.route('/domains/<domain_name>', methods=['GET', 'DELETE'])
def domain_detail(domain_name):
    domains_data = load_data(DOMAINS_FILE)
    
    if request.method == 'DELETE':
        if domain_name in domains_data:
            del domains_data[domain_name]
            save_data(DOMAINS_FILE, domains_data)
            return jsonify({'message': 'Domain deleted'}), 200
        return jsonify({'error': 'Domain not found'}), 404
    
    if domain_name in domains_data:
        return jsonify(domains_data[domain_name])
    return jsonify({'error': 'Domain not found'}), 404

@app.route('/certificates', methods=['GET', 'POST'])
def certificates():
    certs_data = load_data(CERTS_FILE)
    
    if request.method == 'POST':
        data = request.get_json()
        domain_name = data.get('domain')
        acme_provider = data.get('acme_provider', 'letsencrypt')
        
        if not domain_name:
            return jsonify({'error': 'Domain name is required'}), 400
        
        domains_data = load_data(DOMAINS_FILE)
        if domain_name not in domains_data:
            return jsonify({'error': 'Domain not provisioned'}), 400
        
        certs_data[domain_name] = {
            'acme_provider': acme_provider,
            'issued_at': datetime.utcnow().isoformat(),
            'status': 'issued',
            'expires_at': 'simulated_expiry'
        }
        save_data(CERTS_FILE, certs_data)
        return jsonify({'message': 'Certificate issued', 'domain': domain_name}), 201
    
    return jsonify(certs_data)

@app.route('/certificates/<domain_name>', methods=['GET'])
def certificate_detail(domain_name):
    certs_data = load_data(CERTS_FILE)
    
    if domain_name in certs_data:
        return jsonify(certs_data[domain_name])
    return jsonify({'error': 'Certificate not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/domains/example.com', methods=['GET'])
def _auto_stub_domains_example_com():
    return 'Auto-generated stub for /domains/example.com', 200


@app.route('/certificates/test.com', methods=['GET'])
def _auto_stub_certificates_test_com():
    return 'Auto-generated stub for /certificates/test.com', 200
