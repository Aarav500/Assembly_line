from typing import Any, Dict, List, Optional

import numpy as np

from models.baseline import ModelRegistry, SUPPORTED_MODELS
from storage import MetricsStore


class TrainingService:
    def __init__(self, store: MetricsStore, registry: ModelRegistry):
        self.store = store
        self.registry = registry

    def train(
        self,
        metric: str,
        model_name: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if model_name not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")
        values = self.store.get_values(metric, start_ts=start_ts, end_ts=end_ts, order="asc")
        if len(values) < 10:
            raise ValueError("Not enough data to train (min 10 points)")
        model = self.registry.get_model(metric, model_name)
        result = model.fit(values, params=params)
        model.save()
        return {"status": "trained", **result}


class DetectionService:
    def __init__(self, store: MetricsStore, registry: ModelRegistry):
        self.store = store
        self.registry = registry

    def detect(
        self,
        metric: str,
        samples: Optional[List[Dict[str, Any]]] = None,
        model_name: Optional[str] = None,
        threshold: Optional[float] = None,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Determine data to score
        if samples is not None and len(samples) > 0:
            # Expect list of {ts, value}
            series = samples
        else:
            series = self.store.get_series(metric, start_ts=start_ts, end_ts=end_ts, limit=limit, order="asc")
        if not series:
            raise ValueError("No data to detect on")
        values = [float(s.get("value")) for s in series]

        # Determine model
        if model_name is None:
            # prefer trained models by descending sophistication
            for name in ["iforest", "ocsvm", "elliptic", "lof", "zscore"]:
                if self.registry.model_exists(metric, name):
                    model_name = name
                    break
            if model_name is None:
                raise ValueError("No trained model found for metric; please train first")

        model = self.registry.get_model(metric, model_name)
        if not self.registry.model_exists(metric, model_name):
            raise ValueError(f"Model not found for metric={metric}, model={model_name}. Train it first.")
        model.load()

        pred = model.predict(values, threshold=threshold)
        # Merge results per point
        out = []
        for idx, point in enumerate(series):
            out.append(
                {
                    "ts": int(point.get("ts")),
                    "value": float(point.get("value")),
                    "score": float(pred["scores"][idx]),
                    "is_anomaly": bool(pred["is_anomaly"][idx]),
                }
            )
        num_anom = int(sum(1 for x in out if x["is_anomaly"]))
        return {
            "metric": metric,
            "model": model_name,
            "threshold": float(pred["threshold"]),
            "total": len(out),
            "anomalies": num_anom,
            "results": out,
        }

