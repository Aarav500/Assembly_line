import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, request, jsonify
from promotion import PromotionService, PromotionError
from config import load_config

app = Flask(__name__)
conf = load_config()
promoter = PromotionService(conf)

@app.route('/healthz', methods=['GET'])
def healthz():
    return jsonify({"status": "ok"})

@app.route('/promote', methods=['POST'])
def promote():
    payload = request.get_json(silent=True) or {}

    repository = payload.get('repository')
    tag = payload.get('tag')
    dest_tag = payload.get('destination_tag') or tag
    dry_run = bool(payload.get('dry_run', False))
    force = bool(payload.get('force', False))

    if not repository or not tag:
        return jsonify({"error": "repository and tag are required"}), 400

    try:
        result = promoter.promote(repository=repository, source_ref=tag, dest_ref=dest_tag, dry_run=dry_run, force=force)
        return jsonify({"status": "success", "result": result})
    except PromotionError as e:
        return jsonify({"status": "error", "error": str(e), "details": getattr(e, 'details', None)}), e.http_code
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8080'))
    app.run(host='0.0.0.0', port=port)



def create_app():
    return app


@app.route('/artifacts/staging', methods=['POST'])
def _auto_stub_artifacts_staging():
    return 'Auto-generated stub for /artifacts/staging', 200


@app.route('/artifacts/promote', methods=['POST'])
def _auto_stub_artifacts_promote():
    return 'Auto-generated stub for /artifacts/promote', 200
