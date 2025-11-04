from datetime import datetime
from dateutil import parser as dtparser
from typing import Any, Optional, List, Tuple


def safe_lower(s: Any) -> str:
    try:
        return str(s).lower()
    except Exception:
        return str(s)


class Generalizer:
    def max_level(self) -> int:
        raise NotImplementedError

    def generalize(self, value: Any, level: int) -> Any:
        raise NotImplementedError

    def info_loss(self, level: int) -> float:
        # 0.0 no loss, 1.0 max loss
        raise NotImplementedError


class NumericGeneralizer(Generalizer):
    def __init__(self, vmin: float, vmax: float, levels: Optional[List[int]] = None):
        if vmin is None or vmax is None or vmin == float('inf') or vmax == float('-inf'):
            vmin, vmax = 0.0, 1.0
        if vmax < vmin:
            vmax, vmin = vmin, vmax
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        # levels represent number of bins; level 0 is exact value
        # Example bin counts by level: 0->exact, 1->20, 2->10, 3->5, 4->3, 5->1 (ALL)
        self.level_bins = levels if levels else [None, 20, 10, 5, 3, 1]

    def max_level(self) -> int:
        return len(self.level_bins) - 1

    def _bin_label(self, x: Optional[float], bins: int) -> str:
        if x is None:
            return 'NULL'
        if bins <= 1 or self.vmax == self.vmin:
            return '*'
        width = (self.vmax - self.vmin) / float(bins)
        # Ensure inclusion of vmax
        idx = int(min(bins - 1, max(0, (x - self.vmin) // width)))
        start = self.vmin + idx * width
        end = start + width
        return f"[{start:.4g}-{end:.4g})"

    def generalize(self, value: Any, level: int) -> Any:
        if value is None or value == '':
            return 'NULL'
        if level <= 0:
            return value
        bins = self.level_bins[min(level, self.max_level())]
        try:
            x = float(value)
        except Exception:
            # if it cannot be parsed, treat as categorical-ish
            return '*'
        return self._bin_label(x, bins)

    def info_loss(self, level: int) -> float:
        if level <= 0:
            return 0.0
        if level >= self.max_level():
            return 1.0
        bins = self.level_bins[level]
        # Approximate IL by inverse of bins (coarser -> higher loss)
        return 1.0 - (1.0 / max(1, bins))


class DateGeneralizer(Generalizer):
    # Levels: 0 exact, 1 day, 2 month, 3 year, 4 decade, 5 any
    def __init__(self):
        self.levels = ["exact", "day", "month", "year", "decade", "any"]

    def max_level(self) -> int:
        return len(self.levels) - 1

    def _parse(self, value: Any) -> Optional[datetime]:
        if value is None or value == '':
            return None
        if isinstance(value, datetime):
            return value
        try:
            return dtparser.parse(str(value))
        except Exception:
            return None

    def generalize(self, value: Any, level: int) -> Any:
        if value is None or value == '':
            return 'NULL'
        if level <= 0:
            return str(value)
        level = min(level, self.max_level())
        dt = self._parse(value)
        if dt is None:
            return '*'
        if level == 1:
            return dt.strftime('%Y-%m-%d')
        if level == 2:
            return dt.strftime('%Y-%m')
        if level == 3:
            return dt.strftime('%Y')
        if level == 4:
            year = dt.year
            decade = year - (year % 10)
            return f"{decade}s"
        return '*'

    def info_loss(self, level: int) -> float:
        # Crude IL mapping
        level = max(0, min(level, self.max_level()))
        return [0.0, 0.2, 0.4, 0.6, 0.8, 1.0][level]


class CategoricalGeneralizer(Generalizer):
    def __init__(self, prefix_levels: Optional[List[int]] = None):
        # Level 0 exact, 1 prefix 3, 2 prefix 1, 3 any
        self.prefix_levels = prefix_levels if prefix_levels else [0, 3, 1]

    def max_level(self) -> int:
        # +1 for ANY level
        return len(self.prefix_levels) + 1

    def generalize(self, value: Any, level: int) -> Any:
        if value is None or value == '':
            return 'NULL'
        s = str(value)
        if level <= 0:
            return s
        level = min(level, self.max_level())
        # Last level is ANY
        if level == self.max_level():
            return '*'
        pref = self.prefix_levels[level]
        s_low = safe_lower(s)
        if pref <= 0:
            return '*'
        if len(s_low) <= pref:
            return s_low + '*'
        return s_low[:pref] + '*'

    def info_loss(self, level: int) -> float:
        level = max(0, min(level, self.max_level()))
        if level == 0:
            return 0.0
        if level == self.max_level():
            return 1.0
        # Higher prefix length -> lower loss
        pref = self.prefix_levels[level]
        # normalize roughly assuming avg length 10
        return max(0.0, min(1.0, 1.0 - (pref / 10.0)))


def infer_type(values: List[Any]) -> str:
    # Try numeric
    num_ok = 0
    num_total = 0
    for v in values:
        if v is None or v == '':
            continue
        num_total += 1
        try:
            float(v)
            num_ok += 1
        except Exception:
            pass
    if num_total > 0 and (num_ok / num_total) >= 0.8:
        return 'numeric'

    # Try date
    date_ok = 0
    date_total = 0
    for v in values:
        if v is None or v == '':
            continue
        date_total += 1
        try:
            dtparser.parse(str(v))
            date_ok += 1
        except Exception:
            pass
    if date_total > 0 and (date_ok / date_total) >= 0.6:
        return 'date'

    return 'categorical'


def build_generalizer_for(field: str, values: List[Any], forced_type: Optional[str] = None) -> Generalizer:
    t = forced_type or infer_type(values)
    if t == 'numeric':
        vmin, vmax = float('inf'), float('-inf')
        for v in values:
            if v is None or v == '':
                continue
            try:
                x = float(v)
                vmin = min(vmin, x)
                vmax = max(vmax, x)
            except Exception:
                pass
        return NumericGeneralizer(vmin if vmin != float('inf') else 0.0,
                                  vmax if vmax != float('-inf') else 1.0)
    if t == 'date':
        return DateGeneralizer()
    return CategoricalGeneralizer()

