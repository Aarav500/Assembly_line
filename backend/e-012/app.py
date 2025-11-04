import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request
import os
import hashlib
import time

app = Flask(__name__)

# Simulated CDN cache store
cdn_cache = {}
deployment_version = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]


@app.route('/')
def index():
    return jsonify({
        'message': 'CDN Integration Service',
        'deployment_version': deployment_version
    })


@app.route('/api/content/<path:resource>')
def get_content(resource):
    cache_key = f"{deployment_version}:{resource}"
    
    if cache_key in cdn_cache:
        return jsonify({
            'resource': resource,
            'content': cdn_cache[cache_key],
            'cached': True,
            'version': deployment_version
        })
    
    # Simulate fetching content
    content = f"Content for {resource}"
    cdn_cache[cache_key] = content
    
    return jsonify({
        'resource': resource,
        'content': content,
        'cached': False,
        'version': deployment_version
    })


@app.route('/api/deploy', methods=['POST'])
def deploy():
    global deployment_version, cdn_cache
    
    # Invalidate cache on new deployment
    cdn_cache.clear()
    deployment_version = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    return jsonify({
        'message': 'Deployment successful',
        'new_version': deployment_version,
        'cache_invalidated': True
    }), 201


@app.route('/api/cache/status')
def cache_status():
    return jsonify({
        'cache_size': len(cdn_cache),
        'deployment_version': deployment_version,
        'cached_resources': list(cdn_cache.keys())
    })


@app.route('/api/cache/invalidate', methods=['POST'])
def invalidate_cache():
    data = request.get_json() or {}
    resource = data.get('resource')
    
    if resource:
        cache_key = f"{deployment_version}:{resource}"
        if cache_key in cdn_cache:
            del cdn_cache[cache_key]
            return jsonify({
                'message': f'Cache invalidated for {resource}',
                'resource': resource
            })
        return jsonify({'message': 'Resource not in cache'}), 404
    
    # Invalidate all cache
    cdn_cache.clear()
    return jsonify({'message': 'All cache invalidated'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



def create_app():
    return app


@app.route('/api/content/test.js', methods=['GET'])
def _auto_stub_api_content_test_js():
    return 'Auto-generated stub for /api/content/test.js', 200


@app.route('/api/content/app.js', methods=['GET'])
def _auto_stub_api_content_app_js():
    return 'Auto-generated stub for /api/content/app.js', 200
