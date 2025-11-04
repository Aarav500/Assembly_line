import json
import os
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from exporters.torch_export import validate_onnx as validate_onnx_file
from exporters.tf_export import validate_saved_model as validate_saved_model_dir


def _parse_shape(shape_value: Any) -> List[int]:
    if isinstance(shape_value, list):
        return [int(x) for x in shape_value]
    if isinstance(shape_value, str):
        try:
            return [int(x) for x in json.loads(shape_value)]
        except Exception:
            pass
        try:
            return [int(x) for x in shape_value.strip().split(",")]
        except Exception:
            pass
    raise ValueError("Invalid input_shape; provide a list of ints, JSON string, or comma-separated string")


validate_bp = Blueprint("validate", __name__)


@validate_bp.post("/onnx")
def validate_onnx_endpoint():
    # Supports two modes: multipart file upload or local path
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "file is required in multipart form-data"}), 400
        tmp_dir = os.path.join("artifacts", "_uploads")
        os.makedirs(tmp_dir, exist_ok=True)
        out_path = os.path.join(tmp_dir, f"upload-{os.getpid()}-{os.urandom(6).hex()}.onnx")
        f.save(out_path)
        onnx_path = out_path
        input_shape_val = request.form.get("input_shape", "")
    else:
        data = request.get_json(silent=True) or {}
        onnx_path = data.get("path")
        input_shape_val = data.get("input_shape", "")

    if not onnx_path or not os.path.exists(onnx_path):
        return jsonify({"error": "Valid 'path' to onnx file required"}), 400

    try:
        input_shape = _parse_shape(input_shape_val) if input_shape_val else [1, 3, 224, 224]
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        # Dummy reference output is not needed; this validation only runs the model
        metrics = validate_onnx_file(onnx_path, input_tensor=None, reference_outputs=None, input_shape=input_shape)
        return jsonify({"path": onnx_path, "metrics": metrics})
    except Exception as e:
        return jsonify({"error": f"Validation failed: {e}"}), 500


@validate_bp.post("/tf-savedmodel")
def validate_tf_savedmodel_endpoint():
    data = request.get_json(silent=True) or {}
    sm_path = data.get("path")
    input_shape_val = data.get("input_shape", "")
    if not sm_path or not os.path.exists(sm_path):
        return jsonify({"error": "Valid 'path' to SavedModel directory required"}), 400

    try:
        input_shape = _parse_shape(input_shape_val) if input_shape_val else [1, 28, 28, 1]
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        metrics = validate_saved_model_dir(sm_path, input_array=None, reference_outputs=None, input_shape=input_shape)
        return jsonify({"path": sm_path, "metrics": metrics})
    except Exception as e:
        return jsonify({"error": f"Validation failed: {e}"}), 500

