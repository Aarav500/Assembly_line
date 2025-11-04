#!/usr/bin/env python3
import argparse
import json
import os
from typing import Callable, Iterable, Optional

import numpy as np


def _lazy_import_tf():
    import tensorflow as tf  # type: ignore
    return tf


def build_dummy_model(input_shape=(224, 224, 3), num_classes: int = 10):
    tf = _lazy_import_tf()
    inputs = tf.keras.Input(shape=input_shape)
    x = tf.keras.layers.Rescaling(1.0/255)(inputs)
    x = tf.keras.layers.Conv2D(8, 3, activation='relu')(x)
    x = tf.keras.layers.MaxPool2D()(x)
    x = tf.keras.layers.Conv2D(16, 3, activation='relu')(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(32, activation='relu')(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    return model


def train_dummy(model, steps=10, batch_size=32):
    # Train on random data for demonstration
    x = np.random.randint(0, 256, size=(batch_size,)+model.input_shape[1:], dtype=np.uint8)
    y = np.random.randint(0, model.output_shape[-1], size=(batch_size,), dtype=np.int64)
    model.fit(x, y, epochs=1, batch_size=batch_size, steps_per_epoch=steps, verbose=0)


def representative_dataset_from_dir(data_dir: str, input_shape, num_samples: int = 100) -> Callable[[], Iterable[np.ndarray]]:
    from PIL import Image
    paths = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                paths.append(os.path.join(root, f))
    paths = paths[:num_samples]
    h, w, c = input_shape

    def gen():
        for p in paths:
            img = Image.open(p).convert('RGB') if c == 3 else Image.open(p).convert('L')
            img = img.resize((w, h), Image.BILINEAR)
            arr = np.array(img)
            if c == 1 and arr.ndim == 2:
                arr = arr[..., None]
            arr = arr.astype(np.float32) / 255.0
            arr = np.expand_dims(arr, axis=0)
            yield [arr]
    return gen


def convert_to_tflite(
    model,
    output_path: str,
    mode: str = "dynamic",
    rep_data_dir: Optional[str] = None,
    num_calib: int = 100,
    allow_float_fallback: bool = True,
):
    tf = _lazy_import_tf()

    if isinstance(model, str) and os.path.exists(model):
        # Load saved_model or h5
        if os.path.isdir(model):
            keras_model = tf.keras.models.load_model(model)
        else:
            keras_model = tf.keras.models.load_model(model)
    else:
        keras_model = model

    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    if mode == "full_integer":
        input_shape = keras_model.input_shape[1:4]
        if rep_data_dir:
            converter.representative_dataset = representative_dataset_from_dir(rep_data_dir, input_shape, num_samples=num_calib)
        else:
            # random representative samples
            def rep_gen():
                for _ in range(num_calib):
                    arr = np.random.rand(1, *input_shape).astype(np.float32)
                    yield [arr]
            converter.representative_dataset = rep_gen
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
    elif mode == "dynamic":
        # dynamic range quantization only
        pass
    else:
        raise ValueError("mode must be 'dynamic' or 'full_integer'")

    if allow_float_fallback and mode != "full_integer":
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8,
            tf.lite.OpsSet.TFLITE_BUILTINS,
        ]

    tflite_model = converter.convert()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(tflite_model)

    # return minimal model info
    return {
        "output_path": output_path,
        "mode": mode,
        "input_shape": keras_model.input_shape,
        "output_shape": keras_model.output_shape,
    }


def main():
    parser = argparse.ArgumentParser(description="Quantize a Keras model to TFLite for edge deployment")
    parser.add_argument("--input-model", type=str, default=None, help="Path to Keras SavedModel or .h5. If omitted, a dummy model is created.")
    parser.add_argument("--output", type=str, required=True, help="Output .tflite path")
    parser.add_argument("--mode", choices=["dynamic", "full_integer"], default="dynamic", help="Quantization mode")
    parser.add_argument("--rep-data", type=str, default=None, help="Directory with calibration images for full integer quantization")
    parser.add_argument("--num-calib", type=int, default=100, help="Number of calibration samples")
    parser.add_argument("--train-dummy", action="store_true", help="If building dummy model, run a quick train step")
    parser.add_argument("--num-classes", type=int, default=10, help="Classes for dummy model")
    args = parser.parse_args()

    if args.input_model is None:
        model = build_dummy_model(num_classes=args.num_classes)
        if args.train_dummy:
            train_dummy(model)
    else:
        model = args.input_model

    info = convert_to_tflite(
        model,
        output_path=args.output,
        mode=args.mode,
        rep_data_dir=args.rep_data,
        num_calib=args.num_calib,
    )
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()

