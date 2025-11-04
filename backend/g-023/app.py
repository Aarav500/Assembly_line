import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import os
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from config import settings, setup_integrations
from train import run_training

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("tracker-app")

# Initialize integrations (MLflow tracking URI, etc.)
setup_integrations()


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Experiment Tracker Integration Service",
        "version": "1.0.0",
        "trackers": ["mlflow", "wandb", "none"],
        "endpoints": [
            {"path": "/health", "method": "GET"},
            {"path": "/train", "method": "POST"}
        ]
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/train", methods=["POST"])
def train():
    try:
        payload = request.get_json(force=True, silent=False) or {}

        tracker = (payload.get("tracker") or os.getenv("DEFAULT_TRACKER") or settings.default_tracker).lower()
        experiment_name = payload.get("experiment_name") or os.getenv("DEFAULT_EXPERIMENT") or settings.default_experiment
        run_name = payload.get("run_name") or None
        params = payload.get("params") or {}
        test_size = float(payload.get("test_size") or 0.2)
        random_state = payload.get("random_state")
        log_artifacts = bool(payload.get("log_artifacts", True))

        result = run_training(
            tracker_name=tracker,
            experiment_name=experiment_name,
            run_name=run_name,
            params=params,
            test_size=test_size,
            random_state=random_state,
            log_artifacts=log_artifacts,
        )

        return jsonify({
            "status": "success",
            "tracker": tracker,
            "experiment_name": experiment_name,
            "run_name": run_name,
            "result": result,
        })

    except HTTPException as http_err:
        logger.exception("HTTP error during /train")
        return jsonify({"status": "error", "message": str(http_err)}), http_err.code
    except Exception as e:
        logger.exception("Unhandled error during /train")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host=settings.host, port=settings.port, debug=settings.debug)



def create_app():
    return app


@app.route('/mlflow/log', methods=['POST'])
def _auto_stub_mlflow_log():
    return 'Auto-generated stub for /mlflow/log', 200


@app.route('/wandb/log', methods=['POST'])
def _auto_stub_wandb_log():
    return 'Auto-generated stub for /wandb/log', 200
