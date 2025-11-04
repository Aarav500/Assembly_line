import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

from config import Settings
from storage import MetricsStore
from service import TrainingService, DetectionService, ModelRegistry
from schemas import (
    MetricBatch,
    TrainRequest,
    DetectRequest,
    QueryMetricsRequest,
)

settings = Settings()
store = MetricsStore(settings.DATABASE_PATH)
registry = ModelRegistry(settings.MODEL_STORE_DIR)
trainer = TrainingService(store, registry)
detector = DetectionService(store, registry)

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "1.0.0"})


@app.route("/metrics", methods=["POST"])
def ingest_metrics():
    try:
        payload = request.get_json(force=True, silent=False)
        batch = MetricBatch(**payload)
        count = store.insert_samples(batch.as_rows())
        return jsonify({"inserted": count}), 201
    except Exception as e:
        raise BadRequest(str(e))


@app.route("/metrics", methods=["GET"])
def get_metrics():
    try:
        q = QueryMetricsRequest(**request.args.to_dict())
        rows = store.get_series(
            metric=q.metric,
            start_ts=q.start_ts,
            end_ts=q.end_ts,
            limit=q.limit,
            order=q.order,
        )
        return jsonify({"metric": q.metric, "data": rows})
    except Exception as e:
        raise BadRequest(str(e))


@app.route("/train", methods=["POST"])
def train_model():
    try:
        payload = request.get_json(force=True, silent=False)
        req = TrainRequest(**payload)
        result = trainer.train(
            metric=req.metric,
            model_name=req.model,
            start_ts=req.start_ts,
            end_ts=req.end_ts,
            params=req.params or {},
        )
        return jsonify(result)
    except Exception as e:
        raise BadRequest(str(e))


@app.route("/detect", methods=["POST"])
def detect():
    try:
        payload = request.get_json(force=True, silent=False)
        req = DetectRequest(**payload)
        result = detector.detect(
            metric=req.metric,
            samples=req.samples,
            model_name=req.model,
            threshold=req.threshold,
            start_ts=req.start_ts,
            end_ts=req.end_ts,
            limit=req.limit,
        )
        return jsonify(result)
    except Exception as e:
        raise BadRequest(str(e))


@app.route("/models", methods=["GET"])
def list_models():
    metric = request.args.get("metric")
    if not metric:
        raise BadRequest("metric query parameter is required")
    models = registry.list_models(metric)
    return jsonify({"metric": metric, "models": models})


if __name__ == "__main__":
    os.makedirs(settings.MODEL_STORE_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)



def create_app():
    return app


@app.route('/baseline', methods=['POST'])
def _auto_stub_baseline():
    return 'Auto-generated stub for /baseline', 200
