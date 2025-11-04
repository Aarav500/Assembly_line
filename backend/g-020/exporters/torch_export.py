from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyTorch is required for torch exporters") from e

try:
    import onnx
    import onnxruntime as ort
except Exception as e:  # pragma: no cover
    raise RuntimeError("onnx and onnxruntime are required for ONNX validation") from e


class DummyTorchNet(nn.Module):
    def __init__(self, in_ch: int = 3, num_classes: int = 10):
        super().__init__()
        self.conv1 = nn.Conv2d(in_ch, 16, kernel_size=3, stride=2, padding=1)
        self.bn1 = nn.BatchNorm2d(16)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1)
        self.bn2 = nn.BatchNorm2d(32)
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1)
        self.bn3 = nn.BatchNorm2d(64)
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(64, num_classes)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


def build_dummy_torch_model(input_channels: int = 3, num_classes: int = 10) -> nn.Module:
    model = DummyTorchNet(in_ch=input_channels, num_classes=num_classes)
    model.eval()
    return model


def export_torchscript(model: nn.Module, example_input: torch.Tensor, out_path: str) -> str:
    model.eval()
    with torch.no_grad():
        traced = torch.jit.trace(model, example_input)
        torch.jit.save(traced, out_path)
    return out_path


def export_onnx(
    model: nn.Module,
    example_input: torch.Tensor,
    out_path: str,
    opset_version: int = 13,
    dynamic_axes: bool = True,
) -> str:
    model.eval()
    input_names = ["input"]
    output_names = ["output"]
    dyn_axes = None
    if dynamic_axes:
        dyn_axes = {"input": {0: "batch"}, "output": {0: "batch"}}

    torch.onnx.export(
        model,
        example_input,
        out_path,
        input_names=input_names,
        output_names=output_names,
        opset_version=opset_version,
        do_constant_folding=True,
        dynamic_axes=dyn_axes,
    )
    # Quick model check
    onnx_model = onnx.load(out_path)
    onnx.checker.check_model(onnx_model)
    return out_path


def run_reference(model: nn.Module, input_shape) -> Tuple[torch.Tensor, Tuple[torch.Tensor]]:
    model.eval()
    x = torch.randn(*input_shape, dtype=torch.float32)
    with torch.no_grad():
        y = model(x)
    if not isinstance(y, tuple):
        y = (y,)
    return x, y


def _tensor_to_numpy(t: torch.Tensor) -> np.ndarray:
    return t.detach().cpu().numpy()


def _compare_arrays(a: np.ndarray, b: np.ndarray) -> Dict[str, Any]:
    diff = np.abs(a - b)
    return {
        "max_abs_diff": float(diff.max(initial=0.0)),
        "mean_abs_diff": float(diff.mean() if diff.size else 0.0),
        "shape": list(a.shape),
        "dtype": str(a.dtype),
    }


def validate_torchscript(
    ts_path: str,
    input_tensor: torch.Tensor,
    reference_outputs: Tuple[torch.Tensor],
) -> Dict[str, Any]:
    ts = torch.jit.load(ts_path, map_location="cpu")
    ts.eval()
    with torch.no_grad():
        y_ts = ts(input_tensor)
    if not isinstance(y_ts, tuple):
        y_ts = (y_ts,)

    out = {}
    for i, (ref, got) in enumerate(zip(reference_outputs, y_ts)):
        out[f"output_{i}"] = _compare_arrays(_tensor_to_numpy(ref), _tensor_to_numpy(got))
    return out


def validate_onnx(
    onnx_path: str,
    input_tensor: Optional[torch.Tensor] = None,
    reference_outputs: Optional[Tuple[torch.Tensor]] = None,
    input_shape: Optional[list] = None,
) -> Dict[str, Any]:
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name

    if input_tensor is None:
        if input_shape is None:
            # Derive from model input
            ish = sess.get_inputs()[0].shape
            # Replace any None/str dims with default
            ish = [1 if (d is None or isinstance(d, str)) else int(d) for d in ish]
        else:
            ish = input_shape
        x_np = np.random.randn(*ish).astype(np.float32)
    else:
        x_np = _tensor_to_numpy(input_tensor).astype(np.float32)

    y_ort = sess.run(None, {input_name: x_np})

    results: Dict[str, Any] = {"runtime": "onnxruntime", "outputs": {}}

    if reference_outputs is not None:
        for i, ref in enumerate(reference_outputs):
            results["outputs"][f"output_{i}"] = _compare_arrays(_tensor_to_numpy(ref), y_ort[i])
    else:
        # No reference; report shapes/dtypes
        for i, arr in enumerate(y_ort):
            results["outputs"][f"output_{i}"] = {
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
            }

    return results

