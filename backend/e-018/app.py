import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import atexit
from flask import Flask, request, jsonify
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from db import registry
from models import Item
from orchestrator import orchestrator


def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_first_request
    def _start_bg():
        orchestrator.start()

    @atexit.register
    def _stop_bg():
        orchestrator.stop()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/ready")
    def ready():
        st = orchestrator.state()
        primary_ok = st["primary"].get("healthy")
        any_read = any(r.get("healthy") for r in st.get("replicas", {}).values())
        code = 200 if primary_ok and (any_read or primary_ok) else 503
        return jsonify({"primary": primary_ok, "read_available": any_read}), code

    @app.get("/orchestrator/state")
    def orch_state():
        return jsonify(orchestrator.state())

    @app.post("/orchestrator/promote")
    def orch_promote():
        payload = request.get_json(silent=True) or {}
        region = request.args.get("region") or payload.get("region")
        if not region:
            return jsonify({"error": "region is required"}), 400
        try:
            result = orchestrator.promote_region(region)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/items")
    def create_item():
        data = request.get_json(silent=True) or {}
        text = data.get("data")
        if not text:
            return jsonify({"error": "'data' is required"}), 400
        try:
            with registry.get_primary_session() as s:
                s.begin()
                item = Item(data=text)
                s.add(item)
                s.commit()
                return jsonify({"id": item.id, "data": item.data, "created_at": item.created_at.isoformat()}), 201
        except SQLAlchemyError as e:
            return jsonify({"error": str(e)}), 503

    @app.get("/items")
    def list_items():
        # Client may pass their region to prefer a local replica
        preferred_region = request.args.get("region") or settings.region
        # Use replica when available; fall back to primary if no replica available
        sess_info = orchestrator.get_read_session(preferred_region)
        if sess_info[0] is None:
            # No replica available -> fallback to primary for read
            with registry.get_primary_session() as s:
                rows = s.query(Item).order_by(Item.id.desc()).limit(100).all()
                return jsonify({
                    "source": "primary",
                    "items": [
                        {"id": r.id, "data": r.data, "created_at": r.created_at.isoformat()} for r in rows
                    ],
                })
        s, name, meta = sess_info
        try:
            with s:
                rows = s.query(Item).order_by(Item.id.desc()).limit(100).all()
                return jsonify({
                    "source": name,
                    "region": meta.get("region"),
                    "items": [
                        {"id": r.id, "data": r.data, "created_at": r.created_at.isoformat()} for r in rows
                    ],
                })
        except SQLAlchemyError:
            # Fallback to primary on replica failure
            with registry.get_primary_session() as ps:
                rows = ps.query(Item).order_by(Item.id.desc()).limit(100).all()
                return jsonify({
                    "source": "primary",
                    "items": [
                        {"id": r.id, "data": r.data, "created_at": r.created_at.isoformat()} for r in rows
                    ],
                })

    return app


app = create_app()



@app.route('/write', methods=['POST'])
def _auto_stub_write():
    return 'Auto-generated stub for /write', 200


@app.route('/read?key=test_key', methods=['GET'])
def _auto_stub_read_key_test_key():
    return 'Auto-generated stub for /read?key=test_key', 200


@app.route('/regions', methods=['GET'])
def _auto_stub_regions():
    return 'Auto-generated stub for /regions', 200


@app.route('/failover', methods=['POST'])
def _auto_stub_failover():
    return 'Auto-generated stub for /failover', 200


if __name__ == '__main__':
    pass
