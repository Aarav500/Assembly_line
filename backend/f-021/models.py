import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.metrics.pairwise import cosine_distances
from joblib import dump, load

from storage import Alert, Incident
from features import FeatureBuilder
from config import Config


class NoiseReducer:
    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.model_path = os.path.join(self.model_dir, 'noise_iforest.joblib')
        self.feat_path = os.path.join(self.model_dir, 'feature_builder.joblib')
        self.model: IsolationForest | None = None
        self.features: FeatureBuilder | None = None
        self._load()

    def _load(self):
        if os.path.exists(self.model_path) and os.path.exists(self.feat_path):
            try:
                self.model = load(self.model_path)
                self.features = load(self.feat_path)
            except Exception:
                self.model = None
                self.features = None

    def save(self):
        if self.model is not None and self.features is not None:
            dump(self.model, self.model_path)
            dump(self.features, self.feat_path)

    def is_ready(self) -> bool:
        return self.model is not None and self.features is not None and getattr(self.features, 'is_fit', False)

    def _alert_to_dict(self, a: Alert) -> Dict:
        return {
            'timestamp': a.timestamp,
            'source': a.source,
            'service': a.service,
            'severity': a.severity,
            'category': a.category,
            'message': a.message,
        }

    def fit(self, alerts: List[Alert]) -> Tuple[int, bool]:
        if len(alerts) < Config.MIN_TRAIN_ALERTS:
            return len(alerts), False
        fb = FeatureBuilder(max_text_features=500)
        data = [self._alert_to_dict(a) for a in alerts]
        X = fb.fit_transform(data)
        # IsolationForest learns "normal". Frequent duplicates become inliers => considered noise.
        model = IsolationForest(n_estimators=200, max_samples='auto', contamination='auto', random_state=42, n_jobs=-1)
        model.fit(X)
        self.model = model
        self.features = fb
        self.save()
        return len(alerts), True

    def score(self, alert: Alert) -> Tuple[float, bool]:
        if not self.is_ready():
            # Heuristic fallback
            sev = (alert.severity or '').lower()
            is_noise = sev in ('info', 'low', 'minor')
            return 0.0, is_noise
        X = self.features.transform([self._alert_to_dict(alert)])
        score = float(self.model.decision_function(X)[0])  # higher => more normal
        is_noise = score >= Config.NOISE_DECISION_THRESHOLD
        return score, is_noise


class Correlator:
    def __init__(self, features: FeatureBuilder | None = None):
        self.features = features or FeatureBuilder(max_text_features=500)

    def _alert_to_dict(self, a: Alert) -> Dict:
        return {
            'timestamp': a.timestamp,
            'source': a.source,
            'service': a.service,
            'severity': a.severity,
            'category': a.category,
            'message': a.message,
        }

    def cluster(self, alerts: List[Alert]) -> np.ndarray:
        if not alerts:
            return np.array([])
        # Fit features on current non-noise alerts for best topical separation
        X = self.features.fit_transform([self._alert_to_dict(a) for a in alerts])
        # Use cosine distance based DBSCAN
        clustering = DBSCAN(eps=Config.CLUSTER_EPS, min_samples=Config.CLUSTER_MIN_SAMPLES, metric='cosine', n_jobs=-1)
        labels = clustering.fit_predict(X)
        return labels

    def summarize_cluster(self, alerts: List[Alert]) -> Tuple[str, str]:
        # Basic summary: most common category/service and top tokens from messages
        if not alerts:
            return '', 'unknown'
        from collections import Counter
        cat = Counter([a.category for a in alerts if a.category]).most_common(1)
        svc = Counter([a.service for a in alerts if a.service]).most_common(1)
        sev_rank = {'critical': 5, 'high': 4, 'major': 4, 'medium': 3, 'moderate': 3, 'low': 2, 'minor': 2, 'info': 1}
        max_sev = max(alerts, key=lambda a: sev_rank.get((a.severity or '').lower(), 0)).severity or 'unknown'
        # Top tokens via naive TF
        import re
        tokens = []
        for a in alerts:
            msg = (a.message or '').lower()
            msg = re.sub(r"[^a-z0-9\s]", " ", msg)
            tokens.extend([t for t in msg.split() if len(t) > 3])
        tok = Counter(tokens).most_common(5)
        top_terms = ", ".join([t for t, _ in tok])
        parts = []
        if cat: parts.append(f"cat:{cat[0][0]}")
        if svc: parts.append(f"svc:{svc[0][0]}")
        if top_terms:
            parts.append(f"terms:{top_terms}")
        summary = " | ".join(parts) if parts else "related alerts"
        return summary[:250], max_sev


class ModelManager:
    def __init__(self, model_dir: str):
        self.noise = NoiseReducer(model_dir=model_dir)
        # Correlator uses its own feature builder for clustering on current window
        self.correlator = Correlator()
        self.lock = threading.Lock()

    def fit_noise_model(self, db, min_samples: int = 30) -> Tuple[int, bool]:
        with self.lock:
            alerts = db.query(Alert).order_by(Alert.timestamp.asc()).limit(5000).all()
            total, trained = self.noise.fit(alerts)
            return total, trained

    def score_alert(self, db, alert: Alert) -> Tuple[float, bool, str]:
        with self.lock:
            score, is_noise = self.noise.score(alert)
            return score, is_noise, 'iforest' if self.noise.is_ready() else 'heuristic'

    def assign_incident(self, db, alert: Alert) -> int | None:
        # Re-cluster recent non-noise alerts and assign cluster label
        with self.lock:
            window_start = datetime.utcnow() - timedelta(days=2)
            alerts = db.query(Alert).filter(
                Alert.is_noise == False,  # noqa
                Alert.timestamp >= window_start
            ).order_by(Alert.timestamp.asc()).all()
            if not alerts:
                # Create a new incident for this alert alone
                inc = Incident(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), size=1,
                               severity=alert.severity or 'unknown', summary=(alert.category or 'incident'))
                db.add(inc)
                db.commit()
                alert.incident_id = inc.id
                inc.alerts.append(alert)
                db.add(alert)
                return inc.id

            labels = self.correlator.cluster(alerts)
            # Assign labels to alerts
            label_map: Dict[int, List[Alert]] = {}
            for a, lab in zip(alerts, labels):
                if lab == -1:
                    continue
                label_map.setdefault(int(lab), []).append(a)

            # Try to find cluster for the last alert (the one we just ingested)
            # Because we re-fitted correlator on alerts including this one
            label_for_new = None
            for a, lab in zip(alerts, labels):
                if a.id == alert.id:
                    label_for_new = lab
                    break

            if label_for_new is not None and label_for_new != -1:
                # Check if there is an existing incident with this cluster's majority incident_id
                cluster_alerts = label_map.get(int(label_for_new), [])
                # Majority vote of existing incident IDs
                from collections import Counter
                inc_ids = [a.incident_id for a in cluster_alerts if a.incident_id]
                inc_id = None
                if inc_ids:
                    inc_id = Counter(inc_ids).most_common(1)[0][0]
                    inc = db.query(Incident).get(inc_id)
                    if inc:
                        alert.incident_id = inc.id
                        inc.size = db.query(Alert).filter(Alert.incident_id == inc.id).count() + 1
                        inc.updated_at = datetime.utcnow()
                        # Update summary/severity
                        summary, max_sev = self.correlator.summarize_cluster(cluster_alerts + [alert])
                        inc.summary = summary
                        inc.severity = max_sev
                        db.add(inc)
                        db.add(alert)
                        return inc.id

                # No existing incident, create one for this cluster
                summary, max_sev = self.correlator.summarize_cluster(cluster_alerts)
                inc = Incident(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), size=len(cluster_alerts),
                               severity=max_sev, summary=summary)
                db.add(inc)
                db.commit()
                for a in cluster_alerts:
                    a.incident_id = inc.id
                    db.add(a)
                db.commit()
                return inc.id

            # If outlier (-1) or no cluster, create a single-incident
            inc = Incident(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), size=1,
                           severity=alert.severity or 'unknown', summary=(alert.category or 'incident'))
            db.add(inc)
            db.commit()
            alert.incident_id = inc.id
            db.add(alert)
            return inc.id

    def reindex_incidents(self, db):
        # Re-cluster all recent non-noise alerts and rebuild incidents
        with self.lock:
            window_start = datetime.utcnow() - timedelta(days=7)
            alerts = db.query(Alert).filter(Alert.is_noise == False, Alert.timestamp >= window_start).order_by(Alert.timestamp.asc()).all()  # noqa
            if not alerts:
                return
            labels = self.correlator.cluster(alerts)
            # Drop existing incident links
            for a in alerts:
                a.incident_id = None
                db.add(a)
            db.commit()

            clusters: Dict[int, List[Alert]] = {}
            for a, lab in zip(alerts, labels):
                if lab == -1:
                    # Create single incidents for outliers
                    inc = Incident(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), size=1,
                                   severity=a.severity or 'unknown', summary=(a.category or 'incident'))
                    db.add(inc)
                    db.commit()
                    a.incident_id = inc.id
                    db.add(a)
                    continue
                clusters.setdefault(int(lab), []).append(a)

            db.commit()

            for lab, items in clusters.items():
                summary, max_sev = self.correlator.summarize_cluster(items)
                inc = Incident(created_at=datetime.utcnow(), updated_at=datetime.utcnow(), size=len(items),
                               severity=max_sev, summary=summary)
                db.add(inc)
                db.commit()
                for a in items:
                    a.incident_id = inc.id
                    db.add(a)
                db.commit()

