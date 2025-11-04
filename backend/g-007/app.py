import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import json
from flask import Flask, request, jsonify

from src.train_teacher import train_teacher
from src.distill import distill_student
from src.quantize import quantize_model
from src.inference import predict
from src.data_utils import generate_synthetic_jsonl

app = Flask(__name__)

DEFAULT_DATA_DIR = os.environ.get("DATA_DIR", "data")
DEFAULT_MODELS_DIR = os.environ.get("MODELS_DIR", "models")
os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
os.makedirs(DEFAULT_MODELS_DIR, exist_ok=True)

@app.route("/health", methods=["GET"]) 
def health():
    return jsonify({"status": "ok"})

@app.route("/generate_synthetic", methods=["POST"]) 
def generate_synthetic():
    payload = request.get_json(force=True) or {}
    n_train = int(payload.get("n_train", 1000))
    n_val = int(payload.get("n_val", 200))
    out_dir = payload.get("output_dir", DEFAULT_DATA_DIR)
    os.makedirs(out_dir, exist_ok=True)
    train_path = os.path.join(out_dir, "train.jsonl")
    val_path = os.path.join(out_dir, "val.jsonl")
    generate_synthetic_jsonl(train_path, n_train, seed=42)
    generate_synthetic_jsonl(val_path, n_val, seed=123)
    return jsonify({"train_path": train_path, "val_path": val_path, "samples": {"train": n_train, "val": n_val}})

@app.route("/train/teacher", methods=["POST"]) 
def api_train_teacher():
    payload = request.get_json(force=True) or {}
    train_path = payload.get("train_path", os.path.join(DEFAULT_DATA_DIR, "train.jsonl"))
    val_path = payload.get("val_path", os.path.join(DEFAULT_DATA_DIR, "val.jsonl"))
    out_dir = payload.get("output_dir", DEFAULT_MODELS_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out_path = payload.get("output_path", os.path.join(out_dir, "teacher.pt"))

    config = payload.get("config", {})
    result = train_teacher(train_path=train_path, val_path=val_path, output_path=out_path, config=config)
    return jsonify(result)

@app.route("/train/student", methods=["POST"]) 
def api_train_student():
    payload = request.get_json(force=True) or {}
    teacher_path = payload["teacher_path"]
    train_path = payload.get("train_path", os.path.join(DEFAULT_DATA_DIR, "train.jsonl"))
    val_path = payload.get("val_path", os.path.join(DEFAULT_DATA_DIR, "val.jsonl"))
    out_dir = payload.get("output_dir", DEFAULT_MODELS_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out_path = payload.get("output_path", os.path.join(out_dir, "student.pt"))

    config = payload.get("config", {})
    result = distill_student(teacher_package_path=teacher_path, train_path=train_path, val_path=val_path, output_path=out_path, config=config)
    return jsonify(result)

@app.route("/quantize", methods=["POST"]) 
def api_quantize():
    payload = request.get_json(force=True) or {}
    model_path = payload["model_path"]
    out_dir = payload.get("output_dir", DEFAULT_MODELS_DIR)
    os.makedirs(out_dir, exist_ok=True)
    out_path = payload.get("output_path", os.path.join(out_dir, "quantized.pt"))
    dtype = payload.get("dtype", "qint8")
    result = quantize_model(model_package_path=model_path, output_path=out_path, dtype=dtype)
    return jsonify(result)

@app.route("/infer", methods=["POST"]) 
def api_infer():
    payload = request.get_json(force=True) or {}
    model_path = payload["model_path"]
    texts = payload.get("texts", [])
    batch_size = int(payload.get("batch_size", 32))
    with_probs = bool(payload.get("with_probs", True))
    res = predict(model_package_path=model_path, texts=texts, batch_size=batch_size, with_probs=with_probs)
    return jsonify(res)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)



def create_app():
    return app


@app.route('/inference', methods=['POST'])
def _auto_stub_inference():
    return 'Auto-generated stub for /inference', 200


@app.route('/distill', methods=['POST'])
def _auto_stub_distill():
    return 'Auto-generated stub for /distill', 200


@app.route('/compare', methods=['GET'])
def _auto_stub_compare():
    return 'Auto-generated stub for /compare', 200
