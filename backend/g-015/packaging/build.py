#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import zipfile
from datetime import datetime

import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except Exception:
    try:
        from tensorflow.lite import Interpreter  # type: ignore
    except Exception as e:
        Interpreter = None  # type: ignore


DEF_PREPROCESSING = {
    "normalize": {"mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0], "scale": 255.0},
    "apply_softmax": False,
    "dequantize_outputs": True,
}


def probe_tflite(model_path: str):
    if Interpreter is None:
        raise RuntimeError("No TFLite interpreter available to probe model. Install tflite-runtime or tensorflow.")
    intr = Interpreter(model_path=model_path)
    intr.allocate_tensors()
    in_d = intr.get_input_details()[0]
    out_d_all = intr.get_output_details()
    info = {
        "input": {
            "shape": list(in_d.get("shape", [])),
            "dtype": str(in_d.get("dtype", "")),
            "quantization": {
                "scale": float((in_d.get("quantization", (0.0, 0))[0]) or 0.0),
                "zero_point": int((in_d.get("quantization", (0.0, 0))[1]) or 0),
            },
        },
        "outputs": [
            {
                "shape": list(od.get("shape", [])),
                "dtype": str(od.get("dtype", "")),
                "quantization": {
                    "scale": float((od.get("quantization", (0.0, 0))[0]) or 0.0),
                    "zero_point": int((od.get("quantization", (0.0, 0))[1]) or 0),
                },
            }
            for od in out_d_all
        ],
    }
    return info


def build_package(model_path: str, outdir: str, name: str, version: str, labels_path: str | None, preprocessing: dict):
    os.makedirs(outdir, exist_ok=True)
    # Copy model
    dst_model = os.path.join(outdir, "model.tflite")
    shutil.copy2(model_path, dst_model)

    # Probe to fill config
    probe = probe_tflite(dst_model)

    config = {
        "name": name,
        "version": version,
        "model_path": "model.tflite",
        "labels_path": "labels.txt" if labels_path else None,
        "preprocessing": preprocessing or DEF_PREPROCESSING,
        "model_info": probe,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    with open(os.path.join(outdir, "model_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    if labels_path:
        shutil.copy2(labels_path, os.path.join(outdir, "labels.txt"))

    # Write a minimal README
    with open(os.path.join(outdir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(
            f"Edge Package: {name}\nVersion: {version}\n\nFiles:\n- model.tflite\n- model_config.json\n- labels.txt (optional)\n\nUsage:\nSet MODEL_PATH to the absolute path of model.tflite and run the Flask server.\n"
        )

    # Zip it
    zip_path = f"{outdir}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(outdir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, start=outdir)
                zf.write(abs_path, arcname=rel_path)
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="Create an edge deployment package from a TFLite model")
    parser.add_argument("--model", required=True, help="Path to .tflite model")
    parser.add_argument("--outdir", required=True, help="Output directory for the package")
    parser.add_argument("--name", default="edge-model", help="Package name")
    parser.add_argument("--version", default="0.1.0", help="Package version")
    parser.add_argument("--labels", default=None, help="Optional labels.txt path")
    parser.add_argument("--preprocessing", default=None, help="JSON string for preprocessing configuration")
    args = parser.parse_args()

    preprocessing = DEF_PREPROCESSING
    if args.preprocessing:
        try:
            user_cfg = json.loads(args.preprocessing)
            preprocessing.update(user_cfg)
        except Exception:
            pass

    zip_path = build_package(args.model, args.outdir, args.name, args.version, args.labels, preprocessing)
    print(json.dumps({"package_dir": args.outdir, "zip": zip_path}, indent=2))


if __name__ == "__main__":
    main()

