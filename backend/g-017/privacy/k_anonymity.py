from typing import Any, Dict, List, Tuple, Optional
from collections import defaultdict
from .generalization import build_generalizer_for


class KAnalyzer:
    def __init__(self, types: Optional[Dict[str, str]] = None):
        self.types = types or {}

    def _build_generalizers(self, data: List[Dict[str, Any]], qids: List[str]):
        gens = {}
        for q in qids:
            values = [row.get(q) for row in data]
            gens[q] = build_generalizer_for(q, values, forced_type=self.types.get(q))
        return gens

    def _generalize_key(self, row: Dict[str, Any], qids: List[str], gens: Dict[str, Any], levels: Dict[str, int]):
        key = []
        for q in qids:
            g = gens[q]
            lvl = levels.get(q, 0)
            key.append(g.generalize(row.get(q), lvl))
        return tuple(key)

    def _group_counts(self, data: List[Dict[str, Any]], qids: List[str], gens: Dict[str, Any], levels: Dict[str, int]):
        groups = defaultdict(list)
        for idx, row in enumerate(data):
            key = self._generalize_key(row, qids, gens, levels)
            groups[key].append(idx)
        return groups

    def analyze(self, data: List[Dict[str, Any]], qids: List[str]) -> Dict[str, Any]:
        gens = self._build_generalizers(data, qids)
        base_levels = {q: 0 for q in qids}
        groups = self._group_counts(data, qids, gens, base_levels)
        sizes = [len(ixs) for ixs in groups.values()]
        min_size = min(sizes) if sizes else 0
        violating = sum(1 for s in sizes if s == min_size)
        sample = []
        for i, (k, v) in enumerate(groups.items()):
            if i >= 20:
                break
            sample.append({
                'key': {qids[j]: k[j] for j in range(len(qids))},
                'size': len(v)
            })
        return {
            'min_class_size': min_size,
            'equivalence_class_count': len(groups),
            'violating_class_count': sum(1 for s in sizes if s < max(sizes) if sizes) if sizes else 0,
            'record_count': len(data),
            'classes_sample': sample,
        }

