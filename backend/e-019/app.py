import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os
import boto3
from datetime import datetime

app = Flask(__name__)

REGIONS = os.getenv('REGIONS', 'us-east-1,us-west-2').split(',')
PRIMARY_REGION = REGIONS[0]
SECONDARY_REGION = REGIONS[1] if len(REGIONS) > 1 else 'us-west-2'

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'region': os.getenv('AWS_REGION', 'unknown'),
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@app.route('/failover', methods=['POST'])
def trigger_failover():
    data = request.get_json() or {}
    target_region = data.get('target_region', SECONDARY_REGION)
    
    try:
        result = perform_failover(target_region)
        return jsonify({
            'status': 'success',
            'message': f'Failover to {target_region} initiated',
            'details': result
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/dns/update', methods=['POST'])
def update_dns():
    data = request.get_json() or {}
    hosted_zone_id = data.get('hosted_zone_id')
    record_name = data.get('record_name')
    new_ip = data.get('new_ip')
    
    if not all([hosted_zone_id, record_name, new_ip]):
        return jsonify({
            'status': 'error',
            'message': 'Missing required parameters'
        }), 400
    
    try:
        result = update_route53_record(hosted_zone_id, record_name, new_ip)
        return jsonify({
            'status': 'success',
            'message': 'DNS record updated',
            'details': result
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'primary_region': PRIMARY_REGION,
        'secondary_region': SECONDARY_REGION,
        'current_region': os.getenv('AWS_REGION', 'unknown'),
        'available_regions': REGIONS
    }), 200

def perform_failover(target_region):
    # Simulated failover logic
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'target_region': target_region,
        'action': 'failover_initiated'
    }

def update_route53_record(hosted_zone_id, record_name, new_ip):
    # Simulated DNS update logic
    return {
        'hosted_zone_id': hosted_zone_id,
        'record_name': record_name,
        'new_ip': new_ip,
        'action': 'dns_updated'
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)



def create_app():
    return app
