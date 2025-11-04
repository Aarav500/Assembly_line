import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from flask import Flask, jsonify
from api.export import export_bp
from api.validate import validate_bp


def create_app():
    app = Flask(__name__)

    app.register_blueprint(export_bp, url_prefix="/export")
    app.register_blueprint(validate_bp, url_prefix="/validate")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))



@app.route('/export/torchscript', methods=['POST'])
def _auto_stub_export_torchscript():
    return 'Auto-generated stub for /export/torchscript', 200


@app.route('/export/onnx', methods=['POST'])
def _auto_stub_export_onnx():
    return 'Auto-generated stub for /export/onnx', 200


@app.route('/validate/onnx', methods=['POST'])
def _auto_stub_validate_onnx():
    return 'Auto-generated stub for /validate/onnx', 200


@app.route('/validate/torchscript', methods=['POST'])
def _auto_stub_validate_torchscript():
    return 'Auto-generated stub for /validate/torchscript', 200
