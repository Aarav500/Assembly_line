import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from codegen.edge_templates import generate_cloudflare_worker, generate_vercel_edge

app = Flask(__name__)

@app.get('/healthz')
def health():
    return {'status': 'ok'}

@app.post('/codegen/edge')
def codegen_edge():
    data = request.get_json(force=True, silent=True) or {}

    platform = (data.get('platform') or '').lower().strip()
    language = (data.get('language') or 'ts').lower().strip()
    backend_url = data.get('backend_url') or 'http://localhost:5000'
    api_prefix = data.get('api_prefix') or '/api/'
    cors_origin = data.get('cors_origin') or '*'
    pass_through_headers = data.get('pass_through_headers') or ['authorization', 'content-type', 'accept', 'x-requested-with']

    if platform not in ('cloudflare-workers', 'vercel-edge'):
        return jsonify({'error': 'platform must be cloudflare-workers or vercel-edge'}), 400

    if language not in ('ts', 'js'):
        return jsonify({'error': 'language must be ts or js'}), 400

    if not api_prefix.startswith('/'):
        api_prefix = '/' + api_prefix
    if not api_prefix.endswith('/'):
        api_prefix = api_prefix + '/'

    if platform == 'cloudflare-workers':
        files = generate_cloudflare_worker(
            backend_url=backend_url,
            api_prefix=api_prefix,
            language=language,
            cors_origin=cors_origin,
            pass_through_headers=pass_through_headers,
        )
    else:
        files = generate_vercel_edge(
            backend_url=backend_url,
            api_prefix=api_prefix,
            language=language,
            cors_origin=cors_origin,
            pass_through_headers=pass_through_headers,
        )

    return jsonify({'files': files})

if __name__ == '__main__':
    app.run(debug=True)



def create_app():
    return app


@app.route('/generate', methods=['POST'])
def _auto_stub_generate():
    return 'Auto-generated stub for /generate', 200
