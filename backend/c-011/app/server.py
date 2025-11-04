import os
from flask import Flask, jsonify, request
import requests

from .state import state, set_state

app = Flask(__name__)


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    user = state["users"].get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404

    profile = None
    downstream = os.environ.get("DOWNSTREAM_BASE_URL")
    if downstream:
        try:
            resp = requests.get(
                f"{downstream.rstrip('/')}/profiles/{user_id}", timeout=2
            )
            if resp.status_code == 200:
                profile = resp.json()
        except Exception:
            # If downstream fails, we still return the user data
            profile = None

    result = {**user, "profile": profile}
    return jsonify(result), 200


@app.route("/_pact/state-change", methods=["POST"])
def pact_state_change():
    # Pact verifier will call this to set up provider states
    payload = request.get_json(silent=True) or {}
    state_name = payload.get("state") or payload.get("State") or payload.get("providerState")
    action = payload.get("action", "setup")

    if action == "teardown":
        state["users"].clear()
        return jsonify({"result": "teardown"}), 200

    if state_name:
        set_state(state_name)
        return jsonify({"result": "ok", "state": state_name}), 200

    return jsonify({"result": "no state provided"}), 400

