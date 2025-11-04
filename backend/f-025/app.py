import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify

from config import DATA_DIR
from storage import (
    ensure_storage,
    save_baseline,
    load_baseline,
    list_baselines,
    save_run,
    load_run,
    list_runs,
    runs_for_baseline,
)
from synthetic import generate_baseline, generate_run_metrics
from detection import detect_regressions

app = Flask(__name__)
ensure_storage()


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@app.route("/api/health", methods=["GET"])  # simple health check
def health():
    return jsonify({"status": "ok", "time": now_iso()})


@app.route("/api/baselines", methods=["POST"])  # create synthetic baseline snapshot
def api_create_baseline():
    body = request.get_json(force=True, silent=True) or {}

    num_metrics = int(body.get("num_metrics", 50))
    metric_prefix = str(body.get("metric_prefix", "metric"))
    seed = body.get("seed")
    mean_range = body.get("mean_range", [50.0, 100.0])
    std_range = body.get("std_range", [1.0, 5.0])

    baseline_core = generate_baseline(
        num_metrics=num_metrics,
        seed=seed,
        mean_range=tuple(mean_range),
        std_range=tuple(std_range),
        metric_prefix=metric_prefix,
    )

    baseline = {
        "id": generate_id("bl"),
        "created_at": now_iso(),
        "config": {
            "num_metrics": num_metrics,
            "metric_prefix": metric_prefix,
            "seed": seed,
            "mean_range": mean_range,
            "std_range": std_range,
        },
        "metrics": baseline_core["metrics"],
    }

    save_baseline(baseline)

    # attach a quick timeline summary (empty at creation)
    baseline_with_summary = dict(baseline)
    baseline_with_summary["timeline"] = {"runs": [], "regressions_over_time": []}

    return jsonify(baseline_with_summary), 201


@app.route("/api/baselines", methods=["GET"])  # list baselines
def api_list_baselines():
    baselines = list_baselines()
    # provide light-weight info and summary counts
    items = []
    for bl in baselines:
        run_list = runs_for_baseline(bl["id"])  # summary only
        items.append({
            "id": bl["id"],
            "created_at": bl.get("created_at"),
            "num_metrics": len(bl.get("metrics", {})),
            "num_runs": len(run_list),
        })
    return jsonify({"baselines": items})


@app.route("/api/baselines/<baseline_id>", methods=["GET"])  # get baseline details + run timeline
def api_get_baseline(baseline_id):
    bl = load_baseline(baseline_id)
    if not bl:
        return jsonify({"error": "baseline_not_found", "baseline_id": baseline_id}), 404
    runs = runs_for_baseline(baseline_id)
    # build simple timeline of regressions over time
    timeline = []
    for r in runs:
        det = r.get("detection", {})
        summary = det.get("summary", {})
        timeline.append({
            "run_id": r["id"],
            "created_at": r.get("created_at"),
            "regressions": summary.get("regressions_count", 0),
            "total_metrics": summary.get("total_metrics", 0),
            "grade": summary.get("grade", "unknown"),
        })
    bl_out = dict(bl)
    bl_out["timeline"] = timeline
    return jsonify(bl_out)


@app.route("/api/runs", methods=["POST"])  # create synthetic run, detect regressions
def api_create_run():
    body = request.get_json(force=True, silent=True) or {}

    baseline_id = body.get("baseline_id")
    if not baseline_id:
        return jsonify({"error": "missing_baseline_id"}), 400

    baseline = load_baseline(baseline_id)
    if not baseline:
        return jsonify({"error": "baseline_not_found", "baseline_id": baseline_id}), 404

    drift = body.get("drift", {})
    seed = body.get("seed")

    # thresholds for detection
    thresholds = body.get("thresholds") or {
        "z_threshold": body.get("z_threshold", 3.0),
        "percent_threshold": body.get("percent_threshold", 0.25),
        "min_std": body.get("min_std", 1e-6),
    }

    metrics = generate_run_metrics(baseline, drift, seed)
    detection = detect_regressions(baseline, metrics, thresholds)

    run = {
        "id": generate_id("run"),
        "created_at": now_iso(),
        "baseline_id": baseline_id,
        "config": {"drift": drift, "seed": seed},
        "metrics": metrics,
        "detection": detection,
    }

    save_run(run)
    return jsonify(run), 201


@app.route("/api/runs", methods=["GET"])  # list runs
def api_list_runs():
    runs = list_runs()
    items = []
    for r in runs:
        det = r.get("detection", {})
        summary = det.get("summary", {})
        items.append({
            "id": r["id"],
            "created_at": r.get("created_at"),
            "baseline_id": r.get("baseline_id"),
            "regressions": summary.get("regressions_count", 0),
            "total_metrics": summary.get("total_metrics", 0),
            "grade": summary.get("grade", "unknown"),
        })
    return jsonify({"runs": items})


@app.route("/api/runs/<run_id>", methods=["GET"])  # get run details
def api_get_run(run_id):
    run = load_run(run_id)
    if not run:
        return jsonify({"error": "run_not_found", "run_id": run_id}), 404
    return jsonify(run)


@app.route("/api/runs/<run_id>/report", methods=["GET"])  # get run detection report only
def api_get_run_report(run_id):
    run = load_run(run_id)
    if not run:
        return jsonify({"error": "run_not_found", "run_id": run_id}), 404
    return jsonify(run.get("detection", {}))


@app.route("/api/compare", methods=["POST"])  # detect regressions for provided metrics against a baseline
def api_compare():
    body = request.get_json(force=True, silent=True) or {}
    baseline_id = body.get("baseline_id")
    metrics = body.get("metrics")
    thresholds = body.get("thresholds") or {
        "z_threshold": 3.0,
        "percent_threshold": 0.25,
        "min_std": 1e-6,
    }
    if not baseline_id or metrics is None:
        return jsonify({"error": "missing_required_fields", "required": ["baseline_id", "metrics"]}), 400

    baseline = load_baseline(baseline_id)
    if not baseline:
        return jsonify({"error": "baseline_not_found", "baseline_id": baseline_id}), 404

    detection = detect_regressions(baseline, metrics, thresholds)
    return jsonify(detection)


@app.route("/api/baselines/<baseline_id>/timeline", methods=["GET"])  # compact timeline data
def api_baseline_timeline(baseline_id):
    bl = load_baseline(baseline_id)
    if not bl:
        return jsonify({"error": "baseline_not_found", "baseline_id": baseline_id}), 404
    runs = runs_for_baseline(baseline_id)
    timeline = []
    for r in sorted(runs, key=lambda x: x.get("created_at", "")):
        det = r.get("detection", {})
        summary = det.get("summary", {})
        timeline.append({
            "t": r.get("created_at"),
            "regressions": summary.get("regressions_count", 0),
            "total": summary.get("total_metrics", 0),
            "grade": summary.get("grade", "unknown"),
            "run_id": r.get("id"),
        })
    return jsonify({"baseline_id": baseline_id, "timeline": timeline})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/baseline/test_metric', methods=['GET', 'POST'])
def _auto_stub_baseline_test_metric():
    return 'Auto-generated stub for /baseline/test_metric', 200


@app.route('/baseline/cpu', methods=['POST'])
def _auto_stub_baseline_cpu():
    return 'Auto-generated stub for /baseline/cpu', 200


@app.route('/detect/cpu', methods=['POST'])
def _auto_stub_detect_cpu():
    return 'Auto-generated stub for /detect/cpu', 200


@app.route('/synthetic', methods=['GET'])
def _auto_stub_synthetic():
    return 'Auto-generated stub for /synthetic', 200
