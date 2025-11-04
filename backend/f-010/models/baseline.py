import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.covariance import EllipticEnvelope
from sklearn.neighbors import LocalOutlierFactor


SUPPORTED_MODELS = ["iforest", "ocsvm", "elliptic", "lof", "zscore"]


@dataclass
class ModelMeta:
    model_name: str
    metric: str
    params: Dict[str, Any]
    n_train: int
    threshold: float
    score_type: str  # description of score
    feature_shape: Tuple[int, ...]

    def to_json(self) -> str:
        d = asdict(self)
        d["feature_shape"] = list(self.feature_shape)
        return json.dumps(d)

    @staticmethod
    def from_json(s: str) -> "ModelMeta":
        d = json.loads(s)
        d["feature_shape"] = tuple(d.get("feature_shape", []))
        return ModelMeta(**d)


class BaselineModel:
    def __init__(self, model_name: str, metric: str, model_store_dir: str):
        if model_name not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")
        self.model_name = model_name
        self.metric = metric
        self.model_store_dir = model_store_dir
        self.estimator = None
        self.meta: Optional[ModelMeta] = None

    @staticmethod
    def _to_X(values: List[float]) -> np.ndarray:
        arr = np.array(values, dtype=float).reshape(-1, 1)
        return arr

    def _model_paths(self) -> Tuple[str, str]:
        base_dir = os.path.join(self.model_store_dir, self.metric)
        os.makedirs(base_dir, exist_ok=True)
        model_path = os.path.join(base_dir, f"{self.model_name}.joblib")
        meta_path = os.path.join(base_dir, f"{self.model_name}.meta.json")
        return model_path, meta_path

    def fit(self, values: List[float], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        X = self._to_X(values)
        n = X.shape[0]
        if n < 10:
            raise ValueError("Not enough data to train (min 10 points)")

        if self.model_name == "iforest":
            contamination = float(params.get("contamination", 0.05))
            est = IsolationForest(
                contamination=contamination,
                random_state=int(params.get("random_state", 42)),
                n_estimators=int(params.get("n_estimators", 200)),
                max_samples=params.get("max_samples", "auto"),
            )
            est.fit(X)
            scores = -est.score_samples(X)
            threshold = float(np.quantile(scores, 1 - contamination))
            self.estimator = est
            self.meta = ModelMeta(
                model_name=self.model_name,
                metric=self.metric,
                params={"contamination": contamination},
                n_train=n,
                threshold=float(threshold),
                score_type="-score_samples (higher is more anomalous)",
                feature_shape=X.shape[1:],
            )
        elif self.model_name == "ocsvm":
            nu = float(params.get("nu", 0.05))
            kernel = params.get("kernel", "rbf")
            gamma = params.get("gamma", "scale")
            est = OneClassSVM(nu=nu, kernel=kernel, gamma=gamma)
            est.fit(X)
            # For OCSVM, decision_function: positive for inliers, negative for outliers
            scores = -est.decision_function(X).ravel()
            threshold = float(np.quantile(scores, 1 - nu))
            self.estimator = est
            self.meta = ModelMeta(
                model_name=self.model_name,
                metric=self.metric,
                params={"nu": nu, "kernel": kernel, "gamma": gamma},
                n_train=n,
                threshold=float(threshold),
                score_type="-decision_function (higher is more anomalous)",
                feature_shape=X.shape[1:],
            )
        elif self.model_name == "elliptic":
            contamination = float(params.get("contamination", 0.05))
            support_fraction = params.get("support_fraction", None)
            est = EllipticEnvelope(contamination=contamination, support_fraction=support_fraction)
            est.fit(X)
            # decision_function: positive inliers, negative outliers
            scores = -est.decision_function(X).ravel()
            threshold = float(np.quantile(scores, 1 - contamination))
            self.estimator = est
            self.meta = ModelMeta(
                model_name=self.model_name,
                metric=self.metric,
                params={"contamination": contamination, "support_fraction": support_fraction},
                n_train=n,
                threshold=float(threshold),
                score_type="-decision_function (higher is more anomalous)",
                feature_shape=X.shape[1:],
            )
        elif self.model_name == "lof":
            contamination = float(params.get("contamination", 0.05))
            n_neighbors = int(params.get("n_neighbors", min(20, max(2, n // 10))))
            est = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination, novelty=True)
            est.fit(X)
            # Using score_samples available in novelty=True; higher is more normal; invert
            scores = -est.score_samples(X).ravel()
            threshold = float(np.quantile(scores, 1 - contamination))
            self.estimator = est
            self.meta = ModelMeta(
                model_name=self.model_name,
                metric=self.metric,
                params={"contamination": contamination, "n_neighbors": n_neighbors},
                n_train=n,
                threshold=float(threshold),
                score_type="-score_samples (higher is more anomalous)",
                feature_shape=X.shape[1:],
            )
        elif self.model_name == "zscore":
            # Robust z-score baseline (median/MAD)
            z_thresh = float(params.get("z_thresh", 3.5))
            med = float(np.median(X))
            mad = float(np.median(np.abs(X - med)))
            mad = max(mad, 1e-9)
            # Store pseudo-estimator as dict
            self.estimator = {"median": med, "mad": mad, "z_thresh": z_thresh}
            self.meta = ModelMeta(
                model_name=self.model_name,
                metric=self.metric,
                params={"z_thresh": z_thresh},
                n_train=n,
                threshold=float(z_thresh),
                score_type="robust_zscore |x-median|/(1.4826*MAD)",
                feature_shape=X.shape[1:],
            )
        else:
            raise ValueError("Unsupported model")

        return {
            "metric": self.metric,
            "model": self.model_name,
            "n_train": n,
            "threshold": float(self.meta.threshold),
            "params": self.meta.params,
        }

    def predict(self, values: List[float], threshold: Optional[float] = None) -> Dict[str, Any]:
        if self.estimator is None or self.meta is None:
            # try to load from disk
            self.load()
        if self.estimator is None or self.meta is None:
            raise ValueError("Model is not trained")

        X = self._to_X(values)
        if self.model_name == "iforest":
            scores = -self.estimator.score_samples(X).ravel()
        elif self.model_name == "ocsvm":
            scores = -self.estimator.decision_function(X).ravel()
        elif self.model_name == "elliptic":
            scores = -self.estimator.decision_function(X).ravel()
        elif self.model_name == "lof":
            scores = -self.estimator.score_samples(X).ravel()
        elif self.model_name == "zscore":
            med = self.estimator["median"]
            mad = self.estimator["mad"]
            scores = np.abs((X.ravel() - med) / (1.4826 * mad))
        else:
            raise ValueError("Unsupported model")

        thr = float(threshold) if threshold is not None else float(self.meta.threshold)
        is_anom = (scores > thr).tolist()
        return {"scores": scores.tolist(), "threshold": thr, "is_anomaly": is_anom}

    def save(self):
        if self.estimator is None or self.meta is None:
            raise ValueError("Nothing to save: train the model first")
        model_path, meta_path = self._model_paths()
        joblib.dump(self.estimator, model_path)
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(self.meta.to_json())
        return {"model_path": model_path, "meta_path": meta_path}

    def load(self):
        model_path, meta_path = self._model_paths()
        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            return None
        self.estimator = joblib.load(model_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            self.meta = ModelMeta.from_json(f.read())
        return {"model_path": model_path, "meta_path": meta_path}


class ModelRegistry:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def model_exists(self, metric: str, model_name: str) -> bool:
        model_path = os.path.join(self.base_dir, metric, f"{model_name}.joblib")
        meta_path = os.path.join(self.base_dir, metric, f"{model_name}.meta.json")
        return os.path.exists(model_path) and os.path.exists(meta_path)

    def list_models(self, metric: str) -> List[Dict[str, Any]]:
        metric_dir = os.path.join(self.base_dir, metric)
        if not os.path.isdir(metric_dir):
            return []
        out = []
        for name in SUPPORTED_MODELS:
            model_path = os.path.join(metric_dir, f"{name}.joblib")
            meta_path = os.path.join(metric_dir, f"{name}.meta.json")
            if os.path.exists(model_path) and os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.loads(f.read())
                    out.append({"model": name, "meta": meta})
                except Exception:
                    out.append({"model": name, "meta": None})
        return out

    def get_model(self, metric: str, model_name: str) -> BaselineModel:
        return BaselineModel(model_name=model_name, metric=metric, model_store_dir=self.base_dir)

