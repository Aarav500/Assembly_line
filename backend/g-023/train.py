from __future__ import annotations
import json
import os
import tempfile
import time
import uuid
from typing import Any, Dict, Optional

import numpy as np
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import joblib

from trackers.trackers import get_tracker
from config import settings


def run_training(
    tracker_name: str,
    experiment_name: str,
    run_name: Optional[str],
    params: Dict[str, Any],
    test_size: float = 0.2,
    random_state: Optional[int] = None,
    log_artifacts: bool = True,
) -> Dict[str, Any]:
    # Defaults for model params
    model_params = {
        "C": 1.0,
        "max_iter": 200,
        "solver": "lbfgs",
        "multi_class": "auto",
        "n_jobs": None,
        **(params or {}),
    }

    # Load data
    data = load_iris()
    X = data.data
    y = data.target

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Build pipeline (scaling + logistic regression)
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(**{k: v for k, v in model_params.items() if k in {"C", "max_iter", "solver", "multi_class", "n_jobs"}})),
    ])

    tracker = get_tracker(tracker_name)

    # Start run
    run_id = tracker.start_run(experiment_name=experiment_name, run_name=run_name, params={
        **model_params,
        "test_size": test_size,
        "random_state": random_state if random_state is not None else "none",
        "dataset": "iris",
    })

    # Log parameters explicitly too
    tracker.log_params(model_params)

    # Train
    start_time = time.time()
    clf.fit(X_train, y_train)
    train_duration = time.time() - start_time

    # Evaluate
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True)

    metrics = {
        "accuracy": acc,
        "train_duration_sec": float(train_duration),
        # Include per-class f1 as example
        **{f"f1_{k}": float(v.get("f1-score", 0.0)) for k, v in report.items() if isinstance(v, dict) and k not in ("accuracy", "macro avg", "weighted avg")},
        "f1_macro": float(report.get("macro avg", {}).get("f1-score", 0.0)),
        "f1_weighted": float(report.get("weighted avg", {}).get("f1-score", 0.0)),
    }

    tracker.log_metrics(metrics)

    artifact_paths = {}

    if log_artifacts:
        with tempfile.TemporaryDirectory(prefix="artifacts_") as tmpdir:
            # Save model
            model_path = os.path.join(tmpdir, "model.joblib")
            joblib.dump(clf, model_path)
            tracker.log_artifact(model_path, name="model")
            artifact_paths["model"] = model_path

            # Save metrics
            metrics_path = os.path.join(tmpdir, "metrics.json")
            with open(metrics_path, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2)
            tracker.log_artifact(metrics_path, name="metrics")
            artifact_paths["metrics"] = metrics_path

    run_url = tracker.get_run_url()
    tracker.end_run()

    # Compose response
    response = {
        "run_id": run_id,
        "run_url": run_url,
        "metrics": metrics,
        "params": model_params,
        "artifact_examples": artifact_paths,  # local temp paths (for debugging); remote locations handled by tracker UI
    }
    return response

