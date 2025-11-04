import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from orchestrator.engine import Engine
from orchestrator.flows import SampleFlow

app = Flask(__name__)

DB_PATH = os.environ.get("ORCH_DB_PATH", os.path.join(os.path.dirname(__file__), "orchestrator.db"))
engine = Engine(storage_path=DB_PATH)
engine.register_flow("sample", SampleFlow())


def response(success=True, data=None, error=None, status=200):
    payload = {"success": success}
    if success:
        payload["data"] = data
    else:
        payload["error"] = error
    return jsonify(payload), status


@app.route("/health", methods=["GET"])
def health():
    return response(True, {"status": "ok"})


@app.route("/flows", methods=["POST"])
def start_flow():
    try:
        body = request.get_json(force=True) or {}
        flow_name = body.get("flow_name")
        if not flow_name:
            return response(False, error="flow_name is required", status=400)
        input_state = body.get("input", {}) or {}
        auto_advance = bool(body.get("auto_advance", False))
        flow_id, flow = engine.start_flow(flow_name, input_state, auto_advance=auto_advance)
        checkpoints = engine.storage.get_checkpoints(flow_id)
        executions = engine.storage.get_executions(flow_id)
        return response(True, {"flow": flow, "checkpoints": checkpoints, "executions": executions})
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows", methods=["GET"])
def list_flows():
    try:
        name = request.args.get("name")
        status_filter = request.args.get("status")
        flows = engine.storage.list_flows(name=name, status=status_filter)
        return response(True, {"flows": flows})
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows/<flow_id>", methods=["GET"])
def get_flow(flow_id):
    try:
        flow = engine.storage.get_flow(flow_id)
        if not flow:
            return response(False, error="flow not found", status=404)
        checkpoints = engine.storage.get_checkpoints(flow_id)
        executions = engine.storage.get_executions(flow_id)
        return response(True, {"flow": flow, "checkpoints": checkpoints, "executions": executions})
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows/<flow_id>/advance", methods=["POST"])
def advance_flow(flow_id):
    try:
        body = request.get_json(silent=True) or {}
        max_steps = int(body.get("max_steps", 10))
        result = engine.advance(flow_id, max_steps=max_steps)
        flow = engine.storage.get_flow(flow_id)
        return response(True, {"advance": result, "flow": flow})
    except ValueError as ve:
        return response(False, error=str(ve), status=400)
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows/<flow_id>/replay", methods=["POST"])
def replay_flow(flow_id):
    try:
        body = request.get_json(force=True) or {}
        from_checkpoint_id = body.get("from_checkpoint_id")
        from_step_index = body.get("from_step_index")
        auto_advance = bool(body.get("auto_advance", True))
        if not from_checkpoint_id and from_step_index is None:
            return response(False, error="Provide from_checkpoint_id or from_step_index", status=400)
        result = engine.replay(flow_id, from_checkpoint_id=from_checkpoint_id, from_step_index=from_step_index, auto_advance=auto_advance)
        flow = engine.storage.get_flow(flow_id)
        checkpoints = engine.storage.get_checkpoints(flow_id)
        return response(True, {"replay": result, "flow": flow, "checkpoints": checkpoints})
    except ValueError as ve:
        return response(False, error=str(ve), status=400)
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows/<flow_id>/signals/<signal_name>", methods=["POST"])
def send_signal(flow_id, signal_name):
    try:
        flow = engine.storage.get_flow(flow_id)
        if not flow:
            return response(False, error="flow not found", status=404)
        body = request.get_json(silent=True)
        # If payload is a dict with key 'value', use that; else use body as value
        value = body.get("value") if isinstance(body, dict) and "value" in body else body
        # Merge into state under the given signal name
        state = flow["state"] or {}
        signals = (state.get("signals") or {})
        signals[signal_name] = value
        state["signals"] = signals
        # For convenience, if the signal name is a top-level flag, also set it
        if isinstance(value, (str, int, float, bool, type(None))):
            state[signal_name] = value
        engine.storage.update_flow(flow_id, state=state)
        engine.storage.add_execution_log(flow_id, step_index=flow.get("current_step_index"), step_name=None, status="signal", message=f"Signal '{signal_name}' received", details={"value": value})
        return response(True, {"flow": engine.storage.get_flow(flow_id)})
    except Exception as e:
        return response(False, error=str(e), status=500)


@app.route("/flows/<flow_id>/cancel", methods=["POST"])
def cancel_flow(flow_id):
    try:
        flow = engine.storage.get_flow(flow_id)
        if not flow:
            return response(False, error="flow not found", status=404)
        engine.storage.update_flow(flow_id, status="canceled")
        engine.storage.add_execution_log(flow_id, step_index=None, step_name=None, status="canceled", message="Flow canceled", details={})
        return response(True, {"flow": engine.storage.get_flow(flow_id)})
    except Exception as e:
        return response(False, error=str(e), status=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



def create_app():
    return app


@app.route('/workflow/start', methods=['POST'])
def _auto_stub_workflow_start():
    return 'Auto-generated stub for /workflow/start', 200
