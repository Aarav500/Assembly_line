import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify
from database import init_db, SessionLocal
from experiment import ExperimentManager
from analysis import analyze_experiment
from models import Experiment, Variant
from synthetic import run_simulation

app = Flask(__name__)
init_db()


def get_db():
    return SessionLocal()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/experiments", methods=["POST"])
def create_experiment():
    db = get_db()
    try:
        data = request.get_json(force=True) or {}
        name = data.get("name")
        metric_name = data.get("metric_name", "purchase")
        variants = data.get("variants", [])
        if not name or not variants:
            return jsonify({"error": "name and variants required"}), 400
        mgr = ExperimentManager(db)
        exp = mgr.create_experiment(name, metric_name, variants)
        return (
            jsonify({
                "id": exp.id,
                "name": exp.name,
                "metric_name": exp.metric_name,
                "status": exp.status,
            }),
            201,
        )
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@app.route("/experiments", methods=["GET"])
def list_experiments():
    db = get_db()
    try:
        exps = db.query(Experiment).all()
        res = []
        for e in exps:
            res.append({"id": e.id, "name": e.name, "metric_name": e.metric_name, "status": e.status})
        return jsonify(res)
    finally:
        db.close()


@app.route("/experiments/<int:experiment_id>", methods=["GET"])
def get_experiment(experiment_id):
    db = get_db()
    try:
        e = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not e:
            return jsonify({"error": "not found"}), 404
        variants = db.query(Variant).filter(Variant.experiment_id == e.id).all()
        return jsonify(
            {
                "id": e.id,
                "name": e.name,
                "metric_name": e.metric_name,
                "status": e.status,
                "variants": [
                    {
                        "id": v.id,
                        "name": v.name,
                        "allocation": v.allocation,
                        "params": v.params,
                    }
                    for v in variants
                ],
            }
        )
    finally:
        db.close()


@app.route("/flag/<string:experiment_name>", methods=["GET"])
def get_flag(experiment_name):
    db = get_db()
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        mgr = ExperimentManager(db)
        exp = mgr.get_experiment_by_name(experiment_name)
        if not exp:
            return jsonify({"error": "experiment not found"}), 404
        variant = mgr.assign_user(exp, user_id)
        return jsonify({"experiment": exp.name, "variant": variant.name, "variant_id": variant.id})
    finally:
        db.close()


@app.route("/assign", methods=["POST"])
def assign():
    db = get_db()
    try:
        data = request.get_json(force=True) or {}
        experiment_id = data.get("experiment_id")
        user_id = data.get("user_id")
        if not experiment_id or not user_id:
            return jsonify({"error": "experiment_id and user_id required"}), 400
        mgr = ExperimentManager(db)
        exp = mgr.get_experiment_by_id(int(experiment_id))
        if not exp:
            return jsonify({"error": "experiment not found"}), 404
        variant = mgr.assign_user(exp, user_id)
        return jsonify({
            "experiment_id": exp.id,
            "user_id": user_id,
            "variant": variant.name,
            "variant_id": variant.id,
        })
    finally:
        db.close()


@app.route("/event", methods=["POST"])
def track_event():
    db = get_db()
    try:
        data = request.get_json(force=True) or {}
        experiment_id = data.get("experiment_id")
        user_id = data.get("user_id")
        event_name = data.get("event_name")
        value = data.get("value")
        if not experiment_id or not user_id or not event_name:
            return jsonify({"error": "experiment_id, user_id, and event_name required"}), 400
        mgr = ExperimentManager(db)
        exp = mgr.get_experiment_by_id(int(experiment_id))
        if not exp:
            return jsonify({"error": "experiment not found"}), 404
        evt = mgr.track_event(exp, user_id, event_name, value=value)
        return jsonify({"status": "ok", "event_id": evt.id})
    finally:
        db.close()


@app.route("/analysis/<int:experiment_id>", methods=["GET"])
def analysis(experiment_id):
    db = get_db()
    try:
        res = analyze_experiment(db, experiment_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@app.route("/simulate", methods=["POST"])
def simulate():
    db = get_db()
    try:
        spec = request.get_json(force=True) or {}
        seed = spec.get("seed")
        res = run_simulation(db, spec, seed=seed)
        analysis_res = analyze_experiment(db, res["experiment_id"])
        return jsonify({"simulation": res, "analysis": analysis_res})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



def create_app():
    return app


@app.route('/track', methods=['POST'])
def _auto_stub_track():
    return 'Auto-generated stub for /track', 200
