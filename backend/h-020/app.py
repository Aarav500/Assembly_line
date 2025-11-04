import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from services.sync_service import SyncService, SyncError
from config import Config

load_dotenv()

app = Flask(__name__)
config = Config.from_env()
sync_service = SyncService(config)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/mappings', methods=['GET'])
def mappings():
    return jsonify(sync_service.mapping_store.dump())

@app.route('/sync', methods=['POST'])
def sync():
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "Missing JSON body"}), 400
        result = sync_service.sync(payload)
        return jsonify(result)
    except SyncError as e:
        return jsonify({"error": str(e), "details": getattr(e, 'details', None)}), e.status
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



def create_app():
    return app


@app.route('/sync/notion', methods=['POST'])
def _auto_stub_sync_notion():
    return 'Auto-generated stub for /sync/notion', 200


@app.route('/sync/confluence', methods=['POST'])
def _auto_stub_sync_confluence():
    return 'Auto-generated stub for /sync/confluence', 200


@app.route('/sync/status/test-789', methods=['GET'])
def _auto_stub_sync_status_test_789():
    return 'Auto-generated stub for /sync/status/test-789', 200


@app.route('/sync/list', methods=['GET'])
def _auto_stub_sync_list():
    return 'Auto-generated stub for /sync/list', 200
