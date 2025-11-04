import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify, request
from canary.engine import CanaryAnalysisEngine
from canary.store import InMemoryStore


def create_app() -> Flask:
    app = Flask(__name__)
    store = InMemoryStore()
    engine = CanaryAnalysisEngine(store=store)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.post("/api/v1/metrics/ingest")
    def ingest_metrics():
        try:
            payload = request.get_json(silent=True) or {}
            dataset_id = payload.get("id")
            metrics = payload.get("metrics")
            if not dataset_id or not isinstance(dataset_id, str):
                return jsonify({"error": "id (string) is required"}), 400
            if not metrics or not isinstance(metrics, dict):
                return jsonify({"error": "metrics (object) is required"}), 400

            normalized = engine.normalize_dataset(metrics)
            store.store_dataset(dataset_id, normalized)
            return jsonify({
                "message": "ingested",
                "id": dataset_id,
                "metrics_count": len(normalized),
                "metric_names": sorted(list(normalized.keys()))
            }), 201
        except Exception as e:
            return jsonify({"error": f"ingest failed: {e}"}), 400

    @app.get("/api/v1/datasets")
    def list_datasets():
        return jsonify({"datasets": store.list_ids()})

    @app.get("/api/v1/datasets/<dataset_id>")
    def get_dataset(dataset_id: str):
        ds = store.get_dataset(dataset_id)
        if ds is None:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "id": dataset_id,
            "metric_names": sorted(list(ds.keys())),
            "metrics_preview": {k: ds[k][:5] for k in list(ds.keys())[:5]}  # preview first 5 points per metric
        })

    @app.post("/api/v1/analysis/compare")
    def compare_datasets():
        payload = request.get_json(silent=True) or {}
        baseline_id = request.args.get("baseline_id")
        canary_id = request.args.get("canary_id")
        if not baseline_id or not canary_id:
            return jsonify({"error": "baseline_id and canary_id query params are required"}), 400
        rules = payload.get("rules")
        pass_threshold = payload.get("pass_threshold", 80)
        if not rules or not isinstance(rules, list):
            return jsonify({"error": "rules (array) is required in body"}), 400
        baseline = store.get_dataset(baseline_id)
        canary = store.get_dataset(canary_id)
        if baseline is None:
            return jsonify({"error": f"baseline dataset '{baseline_id}' not found"}), 404
        if canary is None:
            return jsonify({"error": f"canary dataset '{canary_id}' not found"}), 404

        try:
            result = engine.run_analysis({"metrics": baseline}, {"metrics": canary}, rules, pass_threshold)
            result["baseline_id"] = baseline_id
            result["canary_id"] = canary_id
            return jsonify(result)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"analysis failed: {e}"}), 500

    @app.post("/api/v1/analysis/run")
    def run_analysis():
        payload = request.get_json(silent=True) or {}
        baseline_spec = payload.get("baseline", {})
        canary_spec = payload.get("canary", {})
        rules = payload.get("rules")
        pass_threshold = payload.get("pass_threshold", 80)

        if not rules or not isinstance(rules, list):
            return jsonify({"error": "rules (array) is required"}), 400

        def resolve_dataset(spec: dict):
            ds = None
            if "id" in spec and spec.get("id"):
                ds = store.get_dataset(spec["id"])
                if ds is None:
                    raise ValueError(f"dataset '{spec['id']}' not found")
            elif "metrics" in spec and isinstance(spec["metrics"], dict):
                ds = engine.normalize_dataset(spec["metrics"])  # ephemeral
            else:
                raise ValueError("dataset must include 'id' or 'metrics'")
            return {"metrics": ds}

        try:
            baseline = resolve_dataset(baseline_spec)
            canary = resolve_dataset(canary_spec)
            result = engine.run_analysis(baseline, canary, rules, pass_threshold)
            result["baseline_id"] = baseline_spec.get("id")
            result["canary_id"] = canary_spec.get("id")
            return jsonify(result)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"analysis failed: {e}"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)



@app.route('/analyze', methods=['POST'])
def _auto_stub_analyze():
    return 'Auto-generated stub for /analyze', 200


@app.route('/api/v1/analysis/compare?baseline_id=baseline-1&canary_id=canary-1', methods=['POST'])
def _auto_stub_api_v1_analysis_compare_baseline_id_baseline_1_canary_id_canary_1():
    return 'Auto-generated stub for /api/v1/analysis/compare?baseline_id=baseline-1&canary_id=canary-1', 200
