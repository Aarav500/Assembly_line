import os
import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
    TFLITE_BACKEND = "tflite_runtime"
except Exception:
    try:
        from tensorflow.lite import Interpreter  # type: ignore
        TFLITE_BACKEND = "tensorflow.lite"
    except Exception as e:
        Interpreter = None  # type: ignore
        TFLITE_BACKEND = None

from .prepost import (
    preprocess_to_input_dtype,
)


class TFLiteRunner:
    def __init__(self, model_path: str, preprocessing: Optional[Dict[str, Any]] = None):
        if Interpreter is None or TFLITE_BACKEND is None:
            raise RuntimeError(
                "No TFLite interpreter available. Install 'tflite-runtime' for your platform or 'tensorflow'."
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model_path = model_path
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        self.in_details = self.interpreter.get_input_details()
        self.out_details = self.interpreter.get_output_details()

        # assume single input
        self.input_index = self.in_details[0]["index"]
        self.input_shape = tuple(self.in_details[0]["shape"])  # e.g. (1, H, W, C)
        self.input_dtype = self.in_details[0]["dtype"]
        self.input_quant_params = self.in_details[0].get("quantization", (0.0, 0))

        # derive dimensions
        if len(self.input_shape) == 4:
            _, h, w, c = self.input_shape
        elif len(self.input_shape) == 3:
            h, w, c = self.input_shape
        else:
            # fallback
            h = int(self.input_shape[-3]) if len(self.input_shape) >= 3 else 224
            w = int(self.input_shape[-2]) if len(self.input_shape) >= 2 else 224
            c = int(self.input_shape[-1]) if len(self.input_shape) >= 1 else 3
        self.input_height = int(h)
        self.input_width = int(w)
        self.input_channels = int(c)

        self.preprocessing = preprocessing or {}

    def infer(self, x: np.ndarray) -> List[np.ndarray]:
        # Prepare input according to dtype and shape
        x_pre = preprocess_to_input_dtype(
            x,
            target_hw=(self.input_height, self.input_width),
            channels=self.input_channels,
            input_dtype=self.input_dtype,
            input_quant_params=self.input_quant_params,
            preprocessing_cfg=self.preprocessing,
        )
        # add batch dim if missing
        if x_pre.ndim == 3:
            x_pre = np.expand_dims(x_pre, axis=0)
        # handle other shapes: attempt to reshape if needed
        if tuple(x_pre.shape[1:]) != tuple(self.input_shape[1:]):
            try:
                x_pre = x_pre.reshape(self.input_shape)
            except Exception:
                pass

        self.interpreter.set_tensor(self.input_index, x_pre)
        self.interpreter.invoke()

        outputs: List[np.ndarray] = []
        for od in self.out_details:
            out = self.interpreter.get_tensor(od["index"])  # numpy array
            # If quantized output and cfg requests dequantize, do so
            q_scale, q_zero = od.get("quantization", (0.0, 0))
            if self.preprocessing.get("dequantize_outputs", True) and q_scale not in (0.0, None):
                out = (out.astype(np.float32) - float(q_zero)) * float(q_scale)
            # optional softmax
            if self.preprocessing.get("apply_softmax", False):
                # apply along last axis
                e = np.exp(out - np.max(out, axis=-1, keepdims=True))
                out = e / (np.sum(e, axis=-1, keepdims=True) + 1e-9)
            outputs.append(out)
        return outputs

    def export_model_info(self) -> Dict[str, Any]:
        return {
            "model_path": self.model_path,
            "backend": TFLITE_BACKEND,
            "input": {
                "shape": list(self.input_shape),
                "dtype": str(self.input_dtype),
                "quantization": {
                    "scale": float(self.input_quant_params[0] or 0.0),
                    "zero_point": int(self.input_quant_params[1] or 0),
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
                for od in self.out_details
            ],
        }


def load_labels(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

