import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Hello World', 'status': 'ok'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/.well-known/acme-challenge/<token>')
def acme_challenge(token):
    # ACME challenges require plain text response, not JSON
    return token, 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


def create_app():
    return app


@app.route('/healthz', methods=['GET'])
def _auto_stub_healthz():
    return 'Auto-generated stub for /healthz', 200


@app.route('/readyz', methods=['GET'])
def _auto_stub_readyz():
    return 'Auto-generated stub for /readyz', 200
