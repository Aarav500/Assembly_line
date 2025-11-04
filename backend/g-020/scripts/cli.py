import argparse
import json
import os

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
from utils.paths import make_artifact_dir, save_json, zip_dir


def main():
    p = argparse.ArgumentParser(description="Model export packaging and validation CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("torch", help="Export torch to ONNX/TorchScript")
    pt.add_argument("--formats", nargs="+", default=["onnx", "torchscript"], choices=["onnx", "torchscript"])
    pt.add_argument("--input-shape", nargs=4, type=int, default=[1, 3, 224, 224])
    pt.add_argument("--opset", type=int, default=13)
    pt.add_argument("--no-dynamic", action="store_true")

    tfp = sub.add_parser("tf", help="Export TF SavedModel")
    tfp.add_argument("--input-shape", nargs=4, type=int, default=[1, 28, 28, 1])

    args = p.parse_args()

    if args.cmd == "torch":
        model = build_dummy_torch_model(input_channels=args.input_shape[1], num_classes=10)
        art_dir = make_artifact_dir("torch-cli")
        x, yref = torch_run_ref(model, args.input_shape)
        spec = {"framework": "pytorch", "input_shape": args.input_shape, "exports": []}

        if "torchscript" in args.formats:
            ts_path = os.path.join(art_dir, "model_torchscript.pt")
            export_torchscript(model, x, ts_path)
            spec["exports"].append({"format": "torchscript", "path": ts_path})
            ts_metrics = validate_ts_with_ref(ts_path, x, yref)
            print("TorchScript validation:", json.dumps(ts_metrics, indent=2))

        if "onnx" in args.formats:
            onnx_path = os.path.join(art_dir, "model.onnx")
            export_onnx(model, x, onnx_path, opset_version=args.opset, dynamic_axes=(not args.no_dynamic))
            spec["exports"].append({"format": "onnx", "path": onnx_path, "opset": args.opset, "dynamic_axes": not args.no_dynamic})
            onnx_metrics = validate_onnx_with_ref(onnx_path, x, yref)
            print("ONNX validation:", json.dumps(onnx_metrics, indent=2))

        save_json(os.path.join(art_dir, "model.spec.json"), spec)
        zip_dir(art_dir, os.path.join(art_dir, "package.zip"))
        print("Artifacts:", art_dir)

    elif args.cmd == "tf":
        model = build_dummy_tf_model(input_shape=args.input_shape[1:], num_classes=10)
        art_dir = make_artifact_dir("tf-cli")
        x, yref = tf_run_ref(model, args.input_shape)
        sm_dir = os.path.join(art_dir, "saved_model")
        export_saved_model(model, sm_dir)
        spec = {"framework": "tensorflow", "input_shape": args.input_shape, "exports": [{"format": "saved_model", "path": sm_dir}]}
        save_json(os.path.join(art_dir, "model.spec.json"), spec)
        tf_metrics = validate_tf_saved_model(sm_dir, x, yref)
        print("SavedModel validation:", json.dumps(tf_metrics, indent=2))
        zip_dir(art_dir, os.path.join(art_dir, "package.zip"))
        print("Artifacts:", art_dir)


if __name__ == "__main__":
    main()

