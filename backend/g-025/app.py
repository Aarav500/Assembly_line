import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sys
import json
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_file, abort

import numpy as np

from utils import (
    ensure_dir,
    write_json,
    read_json,
    set_seed,
    sha256_file,
    snapshot_code,
    capture_environment,
    zip_dir,
    collect_git_info,
)


APP_NAME = "reproducible-experiment-packs"
DEFAULT_EXPERIMENTS_DIR = os.environ.get("EXPERIMENTS_DIR", "experiments")


class ExperimentManager:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        ensure_dir(self.base_dir)
        self.executor = ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "2")))
        self.tasks = {}
        self.lock = threading.Lock()

    def _new_experiment_id(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        short = uuid.uuid4().hex[:8]
        return f"{ts}-{short}"

    def _experiment_dir(self, exp_id: str) -> Path:
        return self.base_dir / exp_id

    def list_experiments(self):
        exps = []
        if not self.base_dir.exists():
            return exps
        for child in sorted(self.base_dir.iterdir()):
            if child.is_dir():
                status_path = child / "status.json"
                meta_path = child / "metadata.json"
                status = read_json(status_path) if status_path.exists() else {}
                meta = read_json(meta_path) if meta_path.exists() else {}
                exps.append({
                    "id": child.name,
                    "status": status.get("status", "unknown"),
                    "created_at": status.get("created_at"),
                    "name": meta.get("name"),
                    "tags": meta.get("tags", []),
                })
        return exps

    def get_experiment(self, exp_id: str):
        exp_dir = self._experiment_dir(exp_id)
        if not exp_dir.exists():
            return None
        status = read_json(exp_dir / "status.json") if (exp_dir / "status.json").exists() else {}
        meta = read_json(exp_dir / "metadata.json") if (exp_dir / "metadata.json").exists() else {}
        result = read_json(exp_dir / "result.json") if (exp_dir / "result.json").exists() else {}
        pack_path = exp_dir / "pack.zip"
        return {
            "id": exp_id,
            "status": status,
            "metadata": meta,
            "result": result,
            "pack_exists": pack_path.exists(),
        }

    def create_and_submit_experiment(self, params: dict | None, seed: int | None, name: str | None, tags: list | None):
        params = params or {}
        seed = int(seed) if seed is not None else int(np.random.SeedSequence().entropy)
        tags = tags or []
        exp_id = self._new_experiment_id()
        exp_dir = self._experiment_dir(exp_id)
        ensure_dir(exp_dir)
        ensure_dir(exp_dir / "artifacts")
        ensure_dir(exp_dir / "environment")
        ensure_dir(exp_dir / "code")

        created_at = datetime.utcnow().isoformat() + "Z"
        status = {
            "id": exp_id,
            "status": "queued",
            "created_at": created_at,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        write_json(exp_dir / "status.json", status)

        meta = {
            "id": exp_id,
            "name": name,
            "tags": tags,
            "seed": seed,
            "params": params,
            "app": APP_NAME,
            "created_at": created_at,
        }
        write_json(exp_dir / "metadata.json", meta)
        write_json(exp_dir / "params.json", {"seed": seed, "params": params})

        with self.lock:
            fut = self.executor.submit(self._run_experiment, exp_id, seed, params)
            self.tasks[exp_id] = fut

        return exp_id

    def _update_status(self, exp_dir: Path, **patch):
        status_path = exp_dir / "status.json"
        status = read_json(status_path) if status_path.exists() else {}
        status.update(patch)
        write_json(status_path, status)

    def _run_experiment(self, exp_id: str, seed: int, params: dict):
        exp_dir = self._experiment_dir(exp_id)
        self._update_status(exp_dir, status="running", started_at=datetime.utcnow().isoformat() + "Z")
        error = None
        try:
            # 1) Ensure deterministic run
            set_seed(seed)

            # 2) Run the toy experiment: linear regression via closed-form with ridge
            n_samples = int(params.get("n_samples", 200))
            n_features = int(params.get("n_features", 3))
            noise_std = float(params.get("noise_std", 0.1))
            ridge = float(params.get("ridge", 1e-6))

            rng = np.random.default_rng(seed)
            w_true = rng.normal(0, 1, size=(n_features,))
            b_true = float(rng.normal(0, 1))
            X = rng.normal(0, 1, size=(n_samples, n_features))
            y = X @ w_true + b_true + rng.normal(0, noise_std, size=(n_samples,))

            # Closed-form ridge solution
            XtX = X.T @ X
            XtX_reg = XtX + ridge * np.eye(n_features)
            Xty = X.T @ y
            w_hat = np.linalg.solve(XtX_reg, Xty)
            # Estimate bias: mean residual approach
            b_hat = float(np.mean(y - X @ w_hat))

            y_hat = X @ w_hat + b_hat
            mse = float(np.mean((y - y_hat) ** 2))
            w_l2_error = float(np.linalg.norm(w_true - w_hat))
            b_abs_error = float(abs(b_true - b_hat))

            # Save artifacts
            artifacts_dir = exp_dir / "artifacts"
            np.savez_compressed(artifacts_dir / "dataset.npz", X=X, y=y)
            # Predictions CSV
            with open(artifacts_dir / "predictions.csv", "w", encoding="utf-8") as f:
                f.write("y,y_hat\n")
                for yi, yh in zip(y.tolist(), y_hat.tolist()):
                    f.write(f"{yi},{yh}\n")

            write_json(artifacts_dir / "weights_true.json", {"w_true": w_true.tolist(), "b_true": b_true})
            write_json(artifacts_dir / "weights_estimated.json", {"w_hat": w_hat.tolist(), "b_hat": b_hat})
            metrics = {
                "mse": mse,
                "w_l2_error": w_l2_error,
                "b_abs_error": b_abs_error,
                "n_samples": n_samples,
                "n_features": n_features,
                "noise_std": noise_std,
                "ridge": ridge,
            }
            write_json(artifacts_dir / "metrics.json", metrics)

            # 3) Environment snapshot (python, pip freeze, platform)
            capture_environment(exp_dir)

            # 4) Code snapshot + manifest
            code_manifest = snapshot_code(root_dir=Path(__file__).resolve().parent, dest_dir=exp_dir / "code")
            write_json(exp_dir / "code_manifest.json", code_manifest)

            # 5) Git info (optional)
            git_info = collect_git_info(root_dir=Path(__file__).resolve().parent)

            # 6) Result and metadata enrichment
            result = {
                "experiment_id": exp_id,
                "algorithm": "linear_regression_closed_form",
                "metrics": metrics,
                "artifacts": {
                    "dataset": "artifacts/dataset.npz",
                    "predictions": "artifacts/predictions.csv",
                    "weights_true": "artifacts/weights_true.json",
                    "weights_estimated": "artifacts/weights_estimated.json",
                    "metrics": "artifacts/metrics.json",
                },
            }
            write_json(exp_dir / "result.json", result)

            metadata_path = exp_dir / "metadata.json"
            metadata = read_json(metadata_path)
            metadata.update({
                "code_manifest": code_manifest,
                "git": git_info,
                "completed_at": datetime.utcnow().isoformat() + "Z",
            })
            write_json(metadata_path, metadata)

            # 7) Create reproducible pack
            pack_path = exp_dir / "pack.zip"
            zip_dir(exp_dir, pack_path)
            pack_hash = sha256_file(pack_path)
            with open(exp_dir / "pack.sha256", "w", encoding="utf-8") as f:
                f.write(pack_hash + "\n")

            self._update_status(
                exp_dir,
                status="completed",
                completed_at=datetime.utcnow().isoformat() + "Z",
                error=None,
            )
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            self._update_status(
                exp_dir,
                status="failed",
                completed_at=datetime.utcnow().isoformat() + "Z",
                error=error,
            )
            raise
        finally:
            pass


app = Flask(__name__)
manager = ExperimentManager(Path(DEFAULT_EXPERIMENTS_DIR))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": APP_NAME})


@app.route("/experiments", methods=["GET"])
def list_experiments():
    return jsonify({"experiments": manager.list_experiments()})


@app.route("/experiments", methods=["POST"])
def create_experiment():
    payload = request.get_json(silent=True) or {}
    params = payload.get("params") or {}
    seed = payload.get("seed")
    name = payload.get("name")
    tags = payload.get("tags") or []

    exp_id = manager.create_and_submit_experiment(params=params, seed=seed, name=name, tags=tags)
    exp_url = request.host_url.rstrip("/") + f"/experiments/{exp_id}"
    return jsonify({
        "id": exp_id,
        "status": "queued",
        "links": {
            "self": exp_url,
            "pack": f"{exp_url}/pack",
        },
    }), 201


@app.route("/experiments/<exp_id>", methods=["GET"])
def get_experiment(exp_id):
    info = manager.get_experiment(exp_id)
    if not info:
        abort(404)
    return jsonify(info)


@app.route("/experiments/<exp_id>/pack", methods=["GET"])
def get_pack(exp_id):
    exp_dir = manager._experiment_dir(exp_id)
    pack_path = exp_dir / "pack.zip"
    if not pack_path.exists():
        abort(404, description="Pack not found. Experiment may still be running.")
    return send_file(pack_path, as_attachment=True, download_name=f"{exp_id}.zip")


@app.route("/experiments/<exp_id>/artifacts/<path:filename>", methods=["GET"])
def get_artifact(exp_id, filename):
    exp_dir = manager._experiment_dir(exp_id)
    artifact_path = exp_dir / "artifacts" / filename
    if not artifact_path.exists():
        abort(404)
    return send_file(artifact_path, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = bool(int(os.environ.get("DEBUG", "1")))
    app.run(host=host, port=port, debug=debug)



def create_app():
    return app
