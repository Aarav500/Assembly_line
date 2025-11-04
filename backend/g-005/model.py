import os
import math
import joblib
import random
from datetime import datetime
from typing import List, Dict, Tuple, Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report


class ModelManager:
    def __init__(self, model_path: str, labels: List[str]):
        self.model_path = model_path
        self.labels = labels
        self.pipeline: Pipeline = None
        self._classes_: List[str] = None
        self.is_trained: bool = False
        self.last_trained_at: str = None
        # Try to load existing model
        self._load()

    def _build_pipeline(self) -> Pipeline:
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000, lowercase=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", solver="liblinear")),
        ])
        return pipe

    def _save(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        payload = {
            "pipeline": self.pipeline,
            "labels": self.labels,
            "last_trained_at": self.last_trained_at,
        }
        joblib.dump(payload, self.model_path)

    def _load(self):
        if os.path.exists(self.model_path):
            try:
                payload = joblib.load(self.model_path)
                self.pipeline = payload.get("pipeline")
                self.labels = payload.get("labels", self.labels)
                self.last_trained_at = payload.get("last_trained_at")
                if self.pipeline is not None:
                    self._classes_ = list(self.pipeline.named_steps["clf"].classes_)
                    self.is_trained = True
            except Exception:
                self.pipeline = None
                self.is_trained = False

    def _can_train(self, labeled: List[Dict[str, Any]]) -> Tuple[bool, str]:
        if not labeled or len(labeled) < 2:
            return False, "Need at least 2 labeled samples."
        classes = set([x.get("label") for x in labeled if x.get("label") is not None])
        if len(classes) < 2:
            return False, "Need at least 2 different classes to train."
        return True, "ok"

    def train(self, labeled: List[Dict[str, Any]]):
        ok, reason = self._can_train(labeled)
        if not ok:
            self.is_trained = False
            return False, {"reason": reason}
        X = [x["text"] for x in labeled]
        y = [x["label"] for x in labeled]
        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X, y)
        self._classes_ = list(self.pipeline.named_steps["clf"].classes_)
        self.is_trained = True
        self.last_trained_at = datetime.utcnow().isoformat() + "Z"
        self._save()
        return True, {"trained_on": len(X), "classes": sorted(list(set(y)))}

    def predict_proba(self, texts: List[str]) -> List[List[float]]:
        if not self.is_trained or self.pipeline is None:
            # uniform probabilities fallback
            k = len(self.labels)
            return [[1.0 / k for _ in self.labels] for _ in texts]
        proba = self.pipeline.predict_proba(texts)
        # Map to configured label order
        idx_map = {c: i for i, c in enumerate(self._classes_)}
        out = []
        for row in proba:
            out.append([float(row[idx_map.get(lbl, 0)]) for lbl in self.labels])
        return out

    def _entropy(self, probs: List[float]) -> float:
        e = 0.0
        for p in probs:
            if p > 0:
                e -= p * math.log(p, 2)
        return e

    def _margin(self, probs: List[float]) -> float:
        # margin = difference between top two class probabilities
        s = sorted(probs, reverse=True)
        if len(s) < 2:
            return 1.0
        return s[0] - s[1]

    def select_samples(self, unlabeled: List[Dict[str, Any]], k: int = 5, strategy: str = "uncertainty") -> List[Dict[str, Any]]:
        if not unlabeled:
            return []
        k = min(k, len(unlabeled))
        texts = [x["text"] for x in unlabeled]
        ids = [x["id"] for x in unlabeled]

        # If not trained, fallback to random
        if not self.is_trained or self.pipeline is None:
            sampled = random.sample(unlabeled, k)
            return [{"id": s["id"], "text": s["text"]} for s in sampled]

        probs = self.predict_proba(texts)
        scored = []
        if strategy == "entropy":
            for sid, text, p in zip(ids, texts, probs):
                scored.append({"id": sid, "text": text, "score": self._entropy(p)})
            scored.sort(key=lambda x: x["score"], reverse=True)
        elif strategy == "margin":
            for sid, text, p in zip(ids, texts, probs):
                scored.append({"id": sid, "text": text, "score": self._margin(p)})
            scored.sort(key=lambda x: x["score"])  # smaller margin = more uncertain
        else:  # default uncertainty = 1 - max prob
            for sid, text, p in zip(ids, texts, probs):
                scored.append({"id": sid, "text": text, "score": 1.0 - max(p)})
            scored.sort(key=lambda x: x["score"], reverse=True)
        return [{"id": s["id"], "text": s["text"], "uncertainty": round(float(s["score"]), 6)} for s in scored[:k]]

    def evaluate(self, test_data: List[Dict[str, Any]]):
        if not self.is_trained or not test_data:
            return None
        X = [x["text"] for x in test_data]
        y_true = [x["label"] for x in test_data]
        y_pred = self.pipeline.predict(X)
        acc = accuracy_score(y_true, y_pred)
        report = classification_report(y_true, y_pred, labels=self.labels, zero_division=0, output_dict=True)
        return {
            "accuracy": float(acc),
            "report": report,
            "last_trained_at": self.last_trained_at,
        }

