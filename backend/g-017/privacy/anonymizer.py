from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from copy import deepcopy

from .generalization import build_generalizer_for, Generalizer


class Anonymizer:
    def __init__(self, types: Optional[Dict[str, str]] = None):
        self.types = types or {}

    def _build_generalizers(self, data: List[Dict[str, Any]], qids: List[str]) -> Dict[str, Generalizer]:
        gens = {}
        for q in qids:
            values = [row.get(q) for row in data]
            gens[q] = build_generalizer_for(q, values, forced_type=self.types.get(q))
        return gens

    def _generalize_key(self, row: Dict[str, Any], qids: List[str], gens: Dict[str, Generalizer], levels: Dict[str, int]):
        key = []
        for q in qids:
            g = gens[q]
            lvl = levels.get(q, 0)
            key.append(g.generalize(row.get(q), lvl))
        return tuple(key)

    def _group(self, data: List[Dict[str, Any]], qids: List[str], gens: Dict[str, Generalizer], levels: Dict[str, int]):
        groups = defaultdict(list)
        for idx, row in enumerate(data):
            key = self._generalize_key(row, qids, gens, levels)
            groups[key].append(idx)
        return groups

    def _min_class_size(self, groups: Dict[Tuple, List[int]]) -> int:
        return min((len(v) for v in groups.values()), default=0)

    def _has_levels_remaining(self, qids: List[str], gens: Dict[str, Generalizer], levels: Dict[str, int]) -> bool:
        for q in qids:
            if levels.get(q, 0) < gens[q].max_level():
                return True
        return False

    def _best_attribute_to_generalize(self, data: List[Dict[str, Any]], qids: List[str], gens: Dict[str, Generalizer], current_levels: Dict[str, int], k: int):
        # Greedy: choose the attribute that reduces violating records the most per unit info loss increase
        base_groups = self._group(data, qids, gens, current_levels)
        violating_indices = set()
        for idxs in base_groups.values():
            if len(idxs) < k:
                violating_indices.update(idxs)
        base_violating = len(violating_indices)

        best = None
        best_score = None
        for q in qids:
            lvl = current_levels.get(q, 0)
            if lvl >= gens[q].max_level():
                continue
            trial_levels = dict(current_levels)
            trial_levels[q] = lvl + 1
            trial_groups = self._group(data, qids, gens, trial_levels)
            trial_violating_indices = set()
            for idxs in trial_groups.values():
                if len(idxs) < k:
                    trial_violating_indices.update(idxs)
            trial_violating = len(trial_violating_indices)
            improvement = base_violating - trial_violating
            il_increase = max(1e-6, gens[q].info_loss(lvl + 1) - gens[q].info_loss(lvl))
            score = improvement / il_increase
            if best is None or score > best_score:
                best = q
                best_score = score
        return best

    def _apply_generalization(self, data: List[Dict[str, Any]], qids: List[str], gens: Dict[str, Generalizer], levels: Dict[str, int]) -> List[Dict[str, Any]]:
        out = []
        for row in data:
            new_row = dict(row)
            for q in qids:
                new_row[q] = gens[q].generalize(row.get(q), levels.get(q, 0))
            out.append(new_row)
        return out

    def _mask_field(self, value: Any, mode: str) -> Any:
        if value is None:
            return None
        s = str(value)
        if mode == 'hash':
            # Non-cryptographic hash for demonstration
            import hashlib
            return hashlib.sha256(s.encode('utf-8')).hexdigest()
        if mode == 'email':
            if '@' in s:
                local, domain = s.split('@', 1)
                if len(local) <= 1:
                    masked_local = '*'
                else:
                    masked_local = local[0] + '*' * (len(local) - 1)
                return masked_local + '@' + domain
            return '*' * max(1, len(s) - 2) + s[-2:]
        if mode == 'phone':
            digits = ''.join(ch for ch in s if ch.isdigit())
            return '***-***-' + digits[-4:] if len(digits) >= 4 else '***'
        if mode == 'last4':
            return ('*' * max(0, len(s) - 4)) + s[-4:]
        if mode == 'full':
            return '*' * len(s)
        # default no masking
        return s

    def _apply_masking(self, data: List[Dict[str, Any]], mask_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not mask_fields:
            return data
        out = []
        for row in data:
            new_row = dict(row)
            for field, mode in mask_fields.items():
                if field in new_row:
                    new_row[field] = self._mask_field(new_row[field], mode)
            out.append(new_row)
        return out

    def anonymize(self,
                  data: List[Dict[str, Any]],
                  quasi_identifiers: List[str],
                  k: int = 5,
                  auto: bool = True,
                  strategies: Optional[Dict[str, Dict[str, Any]]] = None,
                  suppress: bool = True,
                  max_suppression_rate: float = 0.2,
                  mask_fields: Optional[Dict[str, str]] = None,
                  ) -> Dict[str, Any]:
        if not data:
            raise ValueError('Empty dataset')
        gens = self._build_generalizers(data, quasi_identifiers)
        levels = {q: 0 for q in quasi_identifiers}

        # Apply manual strategies first if provided (e.g., set initial levels)
        if strategies:
            for q, strat in strategies.items():
                if q in gens and 'level' in strat:
                    lvl = int(strat['level'])
                    levels[q] = max(0, min(lvl, gens[q].max_level()))

        # Greedy auto generalization
        if auto:
            while True:
                groups = self._group(data, quasi_identifiers, gens, levels)
                min_size = self._min_class_size(groups)
                if min_size >= k:
                    break
                if not self._has_levels_remaining(quasi_identifiers, gens, levels):
                    break
                best_attr = self._best_attribute_to_generalize(data, quasi_identifiers, gens, levels, k)
                if best_attr is None:
                    break
                levels[best_attr] = levels.get(best_attr, 0) + 1

        # Final grouping and suppression if needed
        groups = self._group(data, quasi_identifiers, gens, levels)
        min_size = self._min_class_size(groups)
        violating_keys = [key for key, idxs in groups.items() if len(idxs) < k]
        violating_indices = set(idx for key in violating_keys for idx in groups[key])

        suppressed_indices = []
        anonymized_data = data
        achieved = min_size >= k

        if not achieved and suppress:
            # Remove violating records
            anonymized_data = [r for i, r in enumerate(data) if i not in violating_indices]
            suppressed_indices = sorted(list(violating_indices))
            if len(data) > 0:
                suppression_rate = len(suppressed_indices) / len(data)
            else:
                suppression_rate = 0.0
            if suppression_rate > max_suppression_rate:
                # Rollback suppression
                anonymized_data = data
                suppressed_indices = []
                achieved = False
            else:
                # Recompute groups and min_size on remaining data
                groups = self._group(anonymized_data, quasi_identifiers, gens, levels)
                min_size = self._min_class_size(groups)
                achieved = min_size >= k
        else:
            suppression_rate = 0.0

        # Apply generalization to QIs on the retained dataset
        transformed = self._apply_generalization(anonymized_data, quasi_identifiers, gens, levels)

        # Apply masking on non-QI fields if requested
        transformed = self._apply_masking(transformed, mask_fields or {})

        # Info loss summary
        avg_il = 0.0
        for q in quasi_identifiers:
            lvl = levels.get(q, 0)
            il = gens[q].info_loss(lvl)
            avg_il += il
        avg_il = avg_il / max(1, len(quasi_identifiers))

        return {
            'achieved_k': achieved,
            'k': k,
            'levels': levels,
            'min_class_size': min_size,
            'suppressed_count': len(suppressed_indices),
            'suppression_rate': suppression_rate,
            'data': transformed,
            'info_loss': {
                'average': avg_il,
                'per_attribute': {q: gens[q].info_loss(levels.get(q, 0)) for q in quasi_identifiers}
            }
        }

