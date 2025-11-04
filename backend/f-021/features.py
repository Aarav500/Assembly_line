from typing import List, Dict, Tuple
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction import DictVectorizer

SEVERITY_MAP = {
    'critical': 5,
    'high': 4,
    'major': 4,
    'medium': 3,
    'moderate': 3,
    'low': 2,
    'minor': 2,
    'info': 1,
    'informational': 1,
}


def severity_to_int(s: str) -> int:
    if not s:
        return 0
    return SEVERITY_MAP.get(s.lower(), 0)


class FeatureBuilder:
    def __init__(self, max_text_features: int = 500):
        self.text_vec = TfidfVectorizer(max_features=max_text_features, ngram_range=(1, 2), stop_words='english')
        self.meta_vec = DictVectorizer(sparse=True)
        self.is_fit = False

    def _to_meta(self, alert: Dict) -> Dict:
        ts = alert.get('timestamp')
        hour = int(ts.strftime('%H')) if ts is not None else 0
        dow = int(ts.weekday()) if ts is not None else 0
        msg = alert.get('message') or ''
        meta = {
            'source': (alert.get('source') or '').lower(),
            'service': (alert.get('service') or '').lower(),
            'category': (alert.get('category') or '').lower(),
            'severity': str(severity_to_int(alert.get('severity') or '')),
            'hour': str(hour),
            'dow': str(dow),
            'msg_len_bucket': str(len(msg) // 20),
        }
        return meta

    def fit(self, alerts: List[Dict]):
        texts = [(a.get('message') or '') for a in alerts]
        metas = [self._to_meta(a) for a in alerts]
        self.text_vec.fit(texts)
        self.meta_vec.fit(metas)
        self.is_fit = True

    def transform(self, alerts: List[Dict]) -> csr_matrix:
        texts = [(a.get('message') or '') for a in alerts]
        metas = [self._to_meta(a) for a in alerts]
        X_text = self.text_vec.transform(texts)
        X_meta = self.meta_vec.transform(metas)
        X = hstack([X_text, X_meta]).tocsr()
        return X

    def fit_transform(self, alerts: List[Dict]) -> csr_matrix:
        self.fit(alerts)
        return self.transform(alerts)

    def get_feature_names(self) -> List[str]:
        names = []
        try:
            names.extend([f"txt::{w}" for w in self.text_vec.get_feature_names_out()])
        except Exception:
            pass
        try:
            names.extend([f"meta::{w}" for w in self.meta_vec.get_feature_names_out()])
        except Exception:
            pass
        return names

