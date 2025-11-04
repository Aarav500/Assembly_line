import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
import json

app = Flask(__name__)

node_pools = {}
clusters = {}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/api/clusters', methods=['GET', 'POST'])
def manage_clusters():
    if request.method == 'GET':
        return jsonify({'clusters': list(clusters.values())}), 200
    
    data = request.get_json()
    cluster_id = data.get('id')
    cluster_name = data.get('name')
    
    if not cluster_id or not cluster_name:
        return jsonify({'error': 'Missing required fields'}), 400
    
    clusters[cluster_id] = {
        'id': cluster_id,
        'name': cluster_name,
        'region': data.get('region', 'us-east-1'),
        'version': data.get('version', '1.28')
    }
    
    return jsonify(clusters[cluster_id]), 201

@app.route('/api/clusters/<cluster_id>/nodepools', methods=['GET', 'POST'])
def manage_nodepools(cluster_id):
    if cluster_id not in clusters:
        return jsonify({'error': 'Cluster not found'}), 404
    
    if request.method == 'GET':
        pool_list = [p for p in node_pools.values() if p['cluster_id'] == cluster_id]
        return jsonify({'nodepools': pool_list}), 200
    
    data = request.get_json()
    pool_id = data.get('id')
    
    if not pool_id:
        return jsonify({'error': 'Missing nodepool id'}), 400
    
    node_pools[pool_id] = {
        'id': pool_id,
        'cluster_id': cluster_id,
        'name': data.get('name', 'default-pool'),
        'min_nodes': data.get('min_nodes', 1),
        'max_nodes': data.get('max_nodes', 10),
        'current_nodes': data.get('current_nodes', 3),
        'autoscaling_enabled': data.get('autoscaling_enabled', True),
        'instance_type': data.get('instance_type', 't3.medium')
    }
    
    return jsonify(node_pools[pool_id]), 201

@app.route('/api/nodepools/<pool_id>/scale', methods=['PUT'])
def scale_nodepool(pool_id):
    if pool_id not in node_pools:
        return jsonify({'error': 'Nodepool not found'}), 404
    
    data = request.get_json()
    desired_nodes = data.get('desired_nodes')
    
    if desired_nodes is None:
        return jsonify({'error': 'Missing desired_nodes'}), 400
    
    pool = node_pools[pool_id]
    
    if desired_nodes < pool['min_nodes'] or desired_nodes > pool['max_nodes']:
        return jsonify({'error': 'Desired nodes out of autoscaling bounds'}), 400
    
    pool['current_nodes'] = desired_nodes
    return jsonify(pool), 200

@app.route('/api/nodepools/<pool_id>', methods=['GET'])
def get_nodepool(pool_id):
    if pool_id not in node_pools:
        return jsonify({'error': 'Nodepool not found'}), 404
    
    return jsonify(node_pools[pool_id]), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/api/clusters/cluster-2/nodepools', methods=['POST'])
def _auto_stub_api_clusters_cluster_2_nodepools():
    return 'Auto-generated stub for /api/clusters/cluster-2/nodepools', 200


@app.route('/api/nodepools/pool-1/scale', methods=['PUT'])
def _auto_stub_api_nodepools_pool_1_scale():
    return 'Auto-generated stub for /api/nodepools/pool-1/scale', 200
