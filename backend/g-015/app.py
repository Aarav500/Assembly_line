import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import os
import time
from typing import Optional, Tuple

from flask import Flask, jsonify, request
import numpy as np

from edge_infer.runtime import TFLiteRunner, load_labels
from edge_infer.prepost import load_image_from_request


app = Flask(__name__)


def load_config(config_path: str = "config/model_config.json") -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


CONFIG = load_config()
MODEL_PATH = os.environ.get("MODEL_PATH", CONFIG.get("model_path"))
LABELS_PATH = os.environ.get("LABELS_PATH", CONFIG.get("labels_path"))

runner: Optional[TFLiteRunner] = None
labels = None


@app.before_first_request
def init_model():
    global runner, labels
    try:
        if MODEL_PATH is None:
            app.logger.warning("MODEL_PATH not set and no model_path found in config/model_config.json")
            return
        preprocessing = CONFIG.get("preprocessing", {})
        runner = TFLiteRunner(
            MODEL_PATH,
            preprocessing=preprocessing,
        )
        if LABELS_PATH and os.path.exists(LABELS_PATH):
            labels = load_labels(LABELS_PATH)
        app.logger.info("Model loaded: %s", MODEL_PATH)
    except Exception as e:
        app.logger.exception("Failed to initialize model: %s", e)


@app.get("/health")
def health():
    ok = runner is not None
    return jsonify({"ok": ok, "model_loaded": ok, "model_path": MODEL_PATH}), (200 if ok else 503)


@app.post("/infer")
def infer():
    global runner
    if runner is None:
        return jsonify({"error": "Model not loaded"}), 503

    try:
        # Accept image via multipart/form-data or base64 or numeric array
        image_np: Optional[np.ndarray] = None
        if "image" in request.files and request.files["image"]:
            file_storage = request.files["image"]
            image_np = load_image_from_request(
                file_storage.stream.read(),
                target_hw=(runner.input_height, runner.input_width),
                channels=runner.input_channels,
            )
        else:
            data = request.get_json(silent=True) or {}
            if "image_base64" in data:
                image_np = load_image_from_request(
                    data["image_base64"],
                    target_hw=(runner.input_height, runner.input_width),
                    channels=runner.input_channels,
                )
            elif "input" in data:
                arr = np.array(data["input"], dtype=np.float32)
                image_np = arr

        if image_np is None:
            return jsonify({"error": "No input provided. Use multipart 'image' file, 'image_base64', or 'input' array."}), 400

        t0 = time.time()
        outputs = runner.infer(image_np)
        latency_ms = (time.time() - t0) * 1000.0

        # If classification, optionally map to labels
        response = {
            "latency_ms": round(latency_ms, 3),
        }
        # Handle single or multiple outputs
        if len(outputs) == 1:
            out = outputs[0]
            # argmax for classification probabilities
            if out.ndim >= 2 and out.shape[0] == 1:
                out = out[0]
            # If labels exist and output size matches labels, attach top-k
            if labels is not None and out.size == len(labels):
                # top-5
                top_k = min(5, out.size)
                indices = np.argsort(out)[-top_k:][::-1]
                response["predictions"] = [
                    {"label": labels[i], "index": int(i), "score": float(out[i])}
                    for i in indices
                ]
            else:
                response["output"] = out.tolist()
        else:
            response["outputs"] = [o.tolist() for o in outputs]

        return jsonify(response)
    except Exception as e:
        app.logger.exception("Inference error: %s", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # For local debug
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)



def create_app():
    return app


@app.route('/predict', methods=['POST'])
def _auto_stub_predict():
    return 'Auto-generated stub for /predict', 200


@app.route('/model/info', methods=['GET'])
def _auto_stub_model_info():
    return 'Auto-generated stub for /model/info', 200
