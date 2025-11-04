from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import tensorflow as tf
except Exception as e:  # pragma: no cover
    raise RuntimeError("TensorFlow is required for TF exporters") from e


def build_dummy_tf_model(input_shape=(28, 28, 1), num_classes: int = 10) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=input_shape)
    x = tf.keras.layers.Conv2D(16, 3, strides=2, padding="same", activation="relu")(inputs)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(32, 3, strides=2, padding="same", activation="relu")(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(64, 3, strides=2, padding="same", activation="relu")(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    outputs = tf.keras.layers.Dense(num_classes)(x)
    model = tf.keras.Model(inputs, outputs)
    return model


def export_saved_model(model: tf.keras.Model, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    tf.saved_model.save(model, out_dir)
    return out_dir


def run_reference(model: tf.keras.Model, input_shape) -> Tuple[np.ndarray, Tuple[np.ndarray]]:
    # input_shape is [N, H, W, C]
    x = np.random.randn(*input_shape).astype(np.float32)
    y = model(x, training=False).numpy()
    if not isinstance(y, (tuple, list)):
        y = (y,)
    return x, y


def _compare_arrays(a: np.ndarray, b: np.ndarray) -> Dict[str, Any]:
    diff = np.abs(a - b)
    return {
        "max_abs_diff": float(diff.max(initial=0.0)),
        "mean_abs_diff": float(diff.mean() if diff.size else 0.0),
        "shape": list(a.shape),
        "dtype": str(a.dtype),
    }


def validate_saved_model(
    saved_model_dir: str,
    input_array: Optional[np.ndarray] = None,
    reference_outputs: Optional[Tuple[np.ndarray]] = None,
    input_shape: Optional[list] = None,
) -> Dict[str, Any]:
    loaded = tf.saved_model.load(saved_model_dir)
    # Attempt to find a callable; prefer 'serving_default'
    infer = None
    if hasattr(loaded, 'signatures') and 'serving_default' in loaded.signatures:
        infer = loaded.signatures['serving_default']
    else:
        # Fallback: call the object itself if possible
        infer = loaded

    if input_array is None:
        if input_shape is None:
            # default
            input_shape = [1, 28, 28, 1]
        x = np.random.randn(*input_shape).astype(np.float32)
    else:
        x = input_array.astype(np.float32)

    # Run inference
    if callable(infer):
        try:
            # signature-based call expects a dict of tensors
            if hasattr(infer, 'structured_input_signature'):
                # Attempt to infer input key
                sig = infer.structured_input_signature
                if sig and len(sig) == 2:
                    # second element is dict of inputs
                    inputs_dict = sig[1]
                    key = list(inputs_dict.keys())[0]
                    out = infer(tf.convert_to_tensor(x)) if not isinstance(infer, tf.types.experimental.ConcreteFunction) else infer(**{key: tf.convert_to_tensor(x)})
                else:
                    out = infer(tf.convert_to_tensor(x))
            else:
                out = infer(tf.convert_to_tensor(x))
        except TypeError:
            # Try positional call
            out = infer(tf.convert_to_tensor(x))
    else:
        raise RuntimeError("Loaded SavedModel is not callable")

    # Normalize outputs
    if isinstance(out, dict):
        outs = list(out.values())
    elif isinstance(out, (tuple, list)):
        outs = list(out)
    else:
        outs = [out]

    outs = [o.numpy() if hasattr(o, 'numpy') else np.array(o) for o in outs]

    results: Dict[str, Any] = {"runtime": "tensorflow", "outputs": {}}

    if reference_outputs is not None:
        for i, ref in enumerate(reference_outputs):
            results["outputs"][f"output_{i}"] = _compare_arrays(np.array(ref), outs[i])
    else:
        for i, arr in enumerate(outs):
            results["outputs"][f"output_{i}"] = {"shape": list(arr.shape), "dtype": str(arr.dtype)}

    return results

