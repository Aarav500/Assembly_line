import json
import os
from typing import List, Dict, Any
from collections import Counter
from drift.stats import is_number, compute_bin_edges, histogram_proportions


class BaselineManager:
    def __init__(self, path: str, num_bins: int = 10):
        self.path = path
        self.num_bins = num_bins
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._baseline = None
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r') as f:
                    self._baseline = json.load(f)
            except Exception:
                self._baseline = None
        else:
            self._baseline = None

    def get(self) -> Dict[str, Any]:
        return self._baseline

    def set(self, baseline: Dict[str, Any]):
        self._baseline = baseline
        self._save()

    def _save(self):
        with open(self.path, 'w') as f:
            json.dump(self._baseline, f, indent=2)

    def build_baseline(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        # records: [{ 'features': {...}, 'prediction': float }]
        numeric_values: Dict[str, List[float]] = {}
        categorical_values: Dict[str, List[str]] = {}
        preds: List[float] = []

        for r in records:
            feats = r.get('features', {})
            for k, v in feats.items():
                if is_number(v):
                    numeric_values.setdefault(k, []).append(float(v))
                else:
                    categorical_values.setdefault(k, []).append(str(v))
            p = r.get('prediction', None)
            if p is not None and is_number(p):
                preds.append(float(p))

        baseline = {
            'numeric': {},
            'categorical': {},
            'output': {}
        }

        for feat, vals in numeric_values.items():
            edges = compute_bin_edges(vals, self.num_bins)
            props = histogram_proportions(vals, edges)
            baseline['numeric'][feat] = {
                'bin_edges': edges,
                'proportions': props,
                'count': len(vals)
            }

        for feat, vals in categorical_values.items():
            cnt = Counter(vals)
            total = sum(cnt.values()) or 1
            categories = list(cnt.keys())
            # Include OTHER bucket for future unseen categories
            categories_sorted = sorted(categories)
            categories_sorted.append('__OTHER__')
            proportions = [cnt[c] / total for c in categories_sorted if c != '__OTHER__']
            proportions.append(0.0)  # OTHER proportion baseline 0
            baseline['categorical'][feat] = {
                'categories': categories_sorted,
                'proportions': proportions,
                'count': total
            }

        if preds:
            edges = compute_bin_edges(preds, self.num_bins)
            props = histogram_proportions(preds, edges)
            baseline['output'] = {
                'bin_edges': edges,
                'proportions': props,
                'count': len(preds),
                'positive_rate': sum(1 for p in preds if p >= 0.5) / len(preds)
            }
        else:
            baseline['output'] = {}

        return baseline

    def summary(self) -> Dict[str, Any]:
        b = self._baseline
        if not b:
            return {}
        return {
            'num_numeric_features': len(b.get('numeric', {})),
            'num_categorical_features': len(b.get('categorical', {})),
            'has_output': bool(b.get('output')),
            'counts': {
                'numeric': {k: v.get('count', 0) for k, v in b.get('numeric', {}).items()},
                'categorical': {k: v.get('count', 0) for k, v in b.get('categorical', {}).items()},
                'output': b.get('output', {}).get('count', 0)
            }
        }

