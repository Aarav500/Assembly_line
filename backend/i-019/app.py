import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request, abort
from threading import Thread
import time

from datastore import DataStore
from risk_engine import RiskEngine

app = Flask(__name__)

store = DataStore()
engine = RiskEngine()
store.init_sample_data()
engine.recompute_all(store)


def background_simulation():
    # Periodically introduce drift and recompute risks
    while True:
        time.sleep(15)
        store.random_drift()
        engine.recompute_all(store)


@app.before_first_request
def start_background_thread():
    t = Thread(target=background_simulation, daemon=True)
    t.start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/entities", methods=["GET"])
def list_entities():
    q_type = request.args.get("type")
    items = []
    for ent in store.get_all():
        if q_type and ent.get("type") != q_type:
            continue
        items.append({
            "id": ent["id"],
            "name": ent["name"],
            "type": ent["type"],
            "risk": ent.get("risk", {}),
            "criticality": ent.get("criticality"),
            "exposure": ent.get("exposure"),
            "controls": ent.get("controls", {}),
            "last_seen": ent.get("last_seen"),
        })
    # sort by risk score desc
    items.sort(key=lambda x: x.get("risk", {}).get("score", 0), reverse=True)
    return jsonify({"entities": items})


@app.route("/api/entities/<entity_id>", methods=["GET"])
def get_entity(entity_id):
    ent = store.get(entity_id)
    if not ent:
        abort(404)
    return jsonify(ent)


@app.route("/api/entities/<entity_id>/remediate", methods=["POST"])
def remediate_entity(entity_id):
    ent = store.get(entity_id)
    if not ent:
        abort(404)
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if not action:
        return jsonify({"error": "Missing action"}), 400
    result = store.apply_action(entity_id, action)
    if not result["ok"]:
        return jsonify({"error": result.get("error", "Unknown error")}), 400
    # recompute risk for this entity
    engine.recompute_entity(store, entity_id)
    return jsonify(store.get(entity_id))


@app.route("/api/remediation-routes", methods=["GET"])
def remediation_routes():
    return jsonify(engine.remediation_catalog())


@app.route("/api/recompute", methods=["POST"])
def recompute():
    engine.recompute_all(store)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app


@app.route('/api/risks', methods=['GET'])
def _auto_stub_api_risks():
    return 'Auto-generated stub for /api/risks', 200


@app.route('/api/remediate/1', methods=['POST'])
def _auto_stub_api_remediate_1():
    return 'Auto-generated stub for /api/remediate/1', 200


@app.route('/api/risks/1', methods=['GET'])
def _auto_stub_api_risks_1():
    return 'Auto-generated stub for /api/risks/1', 200


@app.route('/api/remediate/999', methods=['POST'])
def _auto_stub_api_remediate_999():
    return 'Auto-generated stub for /api/remediate/999', 200
