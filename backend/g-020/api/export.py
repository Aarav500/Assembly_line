import io
import json
import os
import time
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from utils.paths import make_artifact_dir, save_json, zip_dir
from exporters.torch_export import (
    build_dummy_torch_model,
    export_onnx,
    export_torchscript,
    run_reference as torch_run_ref,
    validate_onnx as validate_onnx_with_ref,
    validate_torchscript as validate_ts_with_ref,
)
from exporters.tf_export import (
    build_dummy_tf_model,
    export_saved_model,
    run_reference as tf_run_ref,
    validate_saved_model as validate_tf_saved_model,
)


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


def _now_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time())}"


export_bp = Blueprint("export", __name__)


@export_bp.post("/torch")
def export_torch():
    body = request.get_json(silent=True) or {}
    model_name = body.get("model", "dummy")
    input_shape = _parse_shape(body.get("input_shape", [1, 3, 224, 224]))
    opset = int(body.get("opset", 13))
    dynamic_axes = bool(body.get("dynamic_axes", True))
    formats = body.get("formats", ["onnx", "torchscript"])

    if len(input_shape) != 4:
        return jsonify({"error": "input_shape must be 4D NCHW for torch"}), 400

    # Build model
    if model_name == "dummy":
        model = build_dummy_torch_model(input_channels=input_shape[1], num_classes=10)
    else:
        return jsonify({"error": f"Unsupported torch model: {model_name}"}), 400

    # Prepare artifact directory
    art_dir = make_artifact_dir(_now_id("torch"))

    # Prepare reference input and outputs
    try:
        ref_input, ref_outputs = torch_run_ref(model, input_shape)
    except Exception as e:
        return jsonify({"error": f"Failed to run reference torch model: {e}"}), 500

    results: Dict[str, Any] = {
        "artifact_dir": art_dir,
        "files": [],
        "metrics": {},
        "spec": {
            "framework": "pytorch",
            "model": model_name,
            "input_shape": input_shape,
            "exports": [],
        },
    }

    # Export TorchScript
    if "torchscript" in formats:
        ts_path = os.path.join(art_dir, "model_torchscript.pt")
        try:
            export_torchscript(model, ref_input, ts_path)
            results["files"].append(ts_path)
            results["spec"]["exports"].append({"format": "torchscript", "path": ts_path})
            ts_metrics = validate_ts_with_ref(ts_path, ref_input, ref_outputs)
            results["metrics"]["torchscript"] = ts_metrics
        except Exception as e:
            results["metrics"]["torchscript_error"] = str(e)

    # Export ONNX
    if "onnx" in formats:
        onnx_path = os.path.join(art_dir, "model.onnx")
        try:
            export_onnx(model, ref_input, onnx_path, opset_version=opset, dynamic_axes=dynamic_axes)
            results["files"].append(onnx_path)
            results["spec"]["exports"].append({
                "format": "onnx",
                "path": onnx_path,
                "opset": opset,
                "dynamic_axes": dynamic_axes,
            })
            onnx_metrics = validate_onnx_with_ref(onnx_path, ref_input, ref_outputs)
            results["metrics"]["onnx"] = onnx_metrics
        except Exception as e:
            results["metrics"]["onnx_error"] = str(e)

    # Save spec and package
    spec_path = os.path.join(art_dir, "model.spec.json")
    save_json(spec_path, results["spec"])
    results["files"].append(spec_path)

    zip_path = os.path.join(art_dir, "package.zip")
    zip_dir(art_dir, zip_path)
    results["files"].append(zip_path)

    return jsonify(results)


@export_bp.post("/tf")
def export_tf():
    body = request.get_json(silent=True) or {}
    model_name = body.get("model", "dummy")
    input_shape = _parse_shape(body.get("input_shape", [1, 28, 28, 1]))

    if len(input_shape) != 4:
        return jsonify({"error": "input_shape must be 4D NHWC for tf"}), 400

    # Build model
    if model_name == "dummy":
        model = build_dummy_tf_model(input_shape=input_shape[1:], num_classes=10)
    else:
        return jsonify({"error": f"Unsupported tf model: {model_name}"}), 400

    art_dir = make_artifact_dir(_now_id("tf"))

    try:
        ref_input, ref_outputs = tf_run_ref(model, input_shape)
    except Exception as e:
        return jsonify({"error": f"Failed to run reference tf model: {e}"}), 500

    results: Dict[str, Any] = {
        "artifact_dir": art_dir,
        "files": [],
        "metrics": {},
        "spec": {
            "framework": "tensorflow",
            "model": model_name,
            "input_shape": input_shape,
            "exports": [],
        },
    }

    # Export SavedModel
    sm_dir = os.path.join(art_dir, "saved_model")
    try:
        export_saved_model(model, sm_dir)
        results["files"].append(sm_dir)
        results["spec"]["exports"].append({"format": "saved_model", "path": sm_dir})
        tf_metrics = validate_tf_saved_model(sm_dir, ref_input, ref_outputs)
        results["metrics"]["saved_model"] = tf_metrics
    except Exception as e:
        results["metrics"]["saved_model_error"] = str(e)

    spec_path = os.path.join(art_dir, "model.spec.json")
    save_json(spec_path, results["spec"])
    results["files"].append(spec_path)

    zip_path = os.path.join(art_dir, "package.zip")
    zip_dir(art_dir, zip_path)
    results["files"].append(zip_path)

    return jsonify(results)

