Edge model packaging for on-device inference (quantized builds)

This template helps you:
- Quantize a Keras model to TensorFlow Lite (.tflite)
- Build a portable edge package
- Run a lightweight Flask inference server that loads a quantized model

Structure:
- packaging/quantize.py: Convert Keras model -> TFLite (dynamic or full-integer quantization)
- packaging/build.py: Bundle model + config + labels into a distributable folder and zip
- edge_infer/: Minimal runtime for TFLite interpreter with preprocessing utilities
- app.py: Flask API with /health and /infer endpoints

Quick start:
1) Quantize a model (dummy example):
   python3 packaging/quantize.py --output dist/example/model.tflite --mode dynamic --train-dummy

   Optional full integer (with calibration data):
   python3 packaging/quantize.py --input-model path/to/model.h5 --output dist/example/model.tflite --mode full_integer --rep-data path/to/images --num-calib 200

2) Package the model:
   python3 packaging/build.py --model dist/example/model.tflite --outdir dist/example --name my-edge-model --version 0.1.0 --labels path/to/labels.txt

3) Run the server:
   export MODEL_PATH=$(pwd)/dist/example/model.tflite
   # optional
   export LABELS_PATH=$(pwd)/dist/example/labels.txt
   python3 app.py

   curl -X POST -F "image=@sample.jpg" http://localhost:8000/infer

Runtime dependencies:
- Flask, NumPy, Pillow
- TFLite backend: install tflite-runtime (recommended for edge) or TensorFlow (includes tf.lite.Interpreter)

Notes:
- The preprocessing in config/model_config.json controls normalization and post-processing (e.g., softmax).
- For int8 models, the runtime will quantize inputs using the model's input quantization parameters if available.
- For uint8 models, raw 0..255 images are passed directly.

