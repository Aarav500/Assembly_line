import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Any, Dict, List

from flask import Flask, jsonify, request

from ab_testing import Experiment, Variation, assign_experiment
from config import GLOBAL_KILL_SWITCH
from feature_flags import FeatureFlag, decide_flag
from storage import RedisStorage
from utils import error_response, now_iso, to_bool, to_float, validate_percentage

app = Flask(__name__)
store = RedisStorage()


@app.route("/health", methods=["GET"])
def health() -> Any:
    ok = store.ping()
    return jsonify({"status": "ok" if ok else "error", "redis": ok, "global_kill_switch": GLOBAL_KILL_SWITCH})


# Feature Flags
@app.route("/flags", methods=["GET"])
def list_flags() -> Any:
    return jsonify(store.list_flags())


@app.route("/flags", methods=["POST"])
def upsert_flag() -> Any:
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name or not isinstance(name, str):
        return error_response("Missing or invalid 'name'", 400)

    try:
        rollout = validate_percentage(to_float(data.get("rollout", 0)))
    except ValueError as e:
        return error_response(str(e), 400)

    flag = FeatureFlag(
        name=name,
        enabled=to_bool(data.get("enabled", False)),
        rollout=rollout,
        kill_switch=to_bool(data.get("kill_switch", False)),
        description=data.get("description"),
        updated_at=now_iso(),
    )
    store.set_flag(name, flag.to_dict())
    return jsonify(flag.to_dict())


@app.route("/flags/<name>", methods=["GET"])
def get_flag(name: str) -> Any:
    cfg = store.get_flag(name)
    if not cfg:
        return error_response("Flag not found", 404)
    return jsonify(cfg)


@app.route("/flags/<name>/kill", methods=["POST"])
def set_flag_kill(name: str) -> Any:
    cfg = store.get_flag(name)
    if not cfg:
        return error_response("Flag not found", 404)
    data = request.get_json(force=True, silent=True) or {}
    kill = to_bool(data.get("kill", True))
    cfg["kill_switch"] = bool(kill)
    cfg["updated_at"] = now_iso()
    store.set_flag(name, cfg)
    return jsonify(cfg)


@app.route("/flags/<name>/rollout", methods=["POST"])
def set_flag_rollout(name: str) -> Any:
    cfg = store.get_flag(name)
    if not cfg:
        return error_response("Flag not found", 404)
    data = request.get_json(force=True, silent=True) or {}
    try:
        rollout = validate_percentage(to_float(data.get("rollout", 0)))
    except ValueError as e:
        return error_response(str(e), 400)
    cfg["rollout"] = rollout
    cfg["updated_at"] = now_iso()
    store.set_flag(name, cfg)
    return jsonify(cfg)


@app.route("/decide/<name>", methods=["GET"])
def decide(name: str) -> Any:
    user_id = request.args.get("user_id")
    if not user_id:
        return error_response("Missing user_id", 400)
    cfg = store.get_flag(name)
    if not cfg:
        return error_response("Flag not found", 404)
    flag = FeatureFlag.from_dict(cfg)
    decision = decide_flag(flag, user_id)
    store.log_decision({
        "type": "flag",
        "name": decision.get("flag"),
        "user_id": decision.get("user_id"),
        "on": int(bool(decision.get("on"))),
        "reason": decision.get("reason"),
        "bucket": str(decision.get("bucket")) if decision.get("bucket") is not None else "",
        "ts": decision.get("timestamp"),
    })
    return jsonify(decision)


# Experiments
@app.route("/experiments", methods=["GET"]) 
def list_experiments() -> Any:
    return jsonify(store.list_experiments())


@app.route("/experiments", methods=["POST"]) 
def upsert_experiment() -> Any:
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name or not isinstance(name, str):
        return error_response("Missing or invalid 'name'", 400)

    vars_in = data.get("variations")
    if not isinstance(vars_in, list) or len(vars_in) == 0:
        return error_response("Variations must be a non-empty list", 400)

    variations: List[Variation] = []
    for v in vars_in:
        if not isinstance(v, dict) or "name" not in v:
            return error_response("Each variation must have a name", 400)
        weight = to_float(v.get("weight", 0))
        variations.append(Variation(name=v["name"], weight=weight))

    try:
        rollout = validate_percentage(to_float(data.get("rollout", 0)))
    except ValueError as e:
        return error_response(str(e), 400)

    exp = Experiment(
        name=name,
        variations=variations,
        enabled=to_bool(data.get("enabled", False)),
        rollout=rollout,
        kill_switch=to_bool(data.get("kill_switch", False)),
        description=data.get("description"),
        updated_at=now_iso(),
    )

    store.set_experiment(name, exp.to_dict())
    return jsonify(exp.to_dict())


@app.route("/experiments/<name>", methods=["GET"]) 
def get_experiment(name: str) -> Any:
    cfg = store.get_experiment(name)
    if not cfg:
        return error_response("Experiment not found", 404)
    return jsonify(cfg)


@app.route("/experiments/<name>/kill", methods=["POST"]) 
def set_experiment_kill(name: str) -> Any:
    cfg = store.get_experiment(name)
    if not cfg:
        return error_response("Experiment not found", 404)
    data = request.get_json(force=True, silent=True) or {}
    kill = to_bool(data.get("kill", True))
    cfg["kill_switch"] = bool(kill)
    cfg["updated_at"] = now_iso()
    store.set_experiment(name, cfg)
    return jsonify(cfg)


@app.route("/experiments/<name>/rollout", methods=["POST"]) 
def set_experiment_rollout(name: str) -> Any:
    cfg = store.get_experiment(name)
    if not cfg:
        return error_response("Experiment not found", 404)
    data = request.get_json(force=True, silent=True) or {}
    try:
        rollout = validate_percentage(to_float(data.get("rollout", 0)))
    except ValueError as e:
        return error_response(str(e), 400)
    cfg["rollout"] = rollout
    cfg["updated_at"] = now_iso()
    store.set_experiment(name, cfg)
    return jsonify(cfg)


@app.route("/assign/<name>", methods=["GET"]) 
def assign(name: str) -> Any:
    user_id = request.args.get("user_id")
    if not user_id:
        return error_response("Missing user_id", 400)
    cfg = store.get_experiment(name)
    if not cfg:
        return error_response("Experiment not found", 404)
    exp = Experiment.from_dict(cfg)
    assignment = assign_experiment(exp, user_id)
    # Log exposures only when in_experiment True
    if assignment.get("in_experiment") and assignment.get("variant") is not None:
        store.log_exposure({
            "experiment": assignment.get("experiment"),
            "user_id": assignment.get("user_id"),
            "variant": assignment.get("variant"),
            "reason": assignment.get("reason"),
            "ts": assignment.get("timestamp"),
        })
    return jsonify(assignment)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



def create_app():
    return app
