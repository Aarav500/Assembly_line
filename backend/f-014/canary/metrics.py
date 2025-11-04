from typing import Iterable, List, Union, Dict, Any
import math

Number = Union[int, float]


def _extract_values(series: Iterable[Any]) -> List[float]:
    values: List[float] = []
    for item in series:
        if item is None:
            continue
        if isinstance(item, (int, float)):
            values.append(float(item))
        elif isinstance(item, dict):
            v = item.get("value")
            if v is None:
                continue
            values.append(float(v))
        else:
            # unsupported item type -> ignore
            continue
    return values


def percentile(values: List[float], q: float) -> float:
    if not values:
        raise ValueError("empty series")
    if q < 0 or q > 100:
        raise ValueError("q must be between 0 and 100")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    # Nearest-rank method
    k = max(1, int(math.ceil((q / 100.0) * len(xs))))
    return xs[k - 1]


def aggregate(series: Iterable[Any], method: str) -> float:
    vals = _extract_values(series)
    if not vals:
        raise ValueError("empty series after filtering")
    method_l = (method or "").lower()
    if method_l in ("mean", "avg"):
        return sum(vals) / len(vals)
    if method_l in ("median", "p50"):
        return percentile(vals, 50)
    if method_l == "p90":
        return percentile(vals, 90)
    if method_l == "p95":
        return percentile(vals, 95)
    if method_l == "p99":
        return percentile(vals, 99)
    if method_l == "min":
        return min(vals)
    if method_l == "max":
        return max(vals)
    if method_l == "sum":
        return float(sum(vals))
    if method_l == "count":
        return float(len(vals))
    if method_l in ("stddev", "stdev"):
        m = sum(vals) / len(vals)
        var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1 if len(vals) > 1 else 1)
        return math.sqrt(var)
    raise ValueError(f"unsupported aggregation method: {method}")


def compute_metric_value(dataset: Dict[str, List[Any]], spec: Dict[str, Any]) -> float:
    if not isinstance(spec, dict):
        raise ValueError("metric spec must be an object")
    calc = (spec.get("calc") or "aggregate").lower()
    if calc == "aggregate":
        name = spec.get("name")
        agg = spec.get("aggregation", "mean")
        if not name or name not in dataset:
            raise ValueError(f"metric '{name}' not found in dataset")
        return aggregate(dataset[name], agg)
    if calc == "rate":
        num = spec.get("numerator") or {}
        den = spec.get("denominator") or {}
        num_v = compute_metric_value(dataset, {"calc": "aggregate", **num})
        den_v = compute_metric_value(dataset, {"calc": "aggregate", **(den)})
        if den_v == 0:
            if num_v == 0:
                return 0.0
            return float("inf")
        return num_v / den_v
    if calc == "expression":
        # Simple safe expression evaluation using provided symbols from dataset aggregations
        # spec: { calc: 'expression', expr: 'errors_sum / requests_sum', symbols: { 'errors_sum': {name:'errors', aggregation:'sum'}, ... } }
        expr = spec.get("expr")
        symbols_spec = spec.get("symbols", {})
        if not expr or not isinstance(symbols_spec, dict):
            raise ValueError("expression spec requires 'expr' and 'symbols'")
        symbols: Dict[str, float] = {}
        for key, s in symbols_spec.items():
            symbols[key] = compute_metric_value(dataset, {"calc": "aggregate", **s})
        # Evaluate with restricted globals/locals
        try:
            return float(eval(expr, {"__builtins__": {}}, symbols))
        except ZeroDivisionError:
            return float("inf")
        except Exception as e:
            raise ValueError(f"expression eval error: {e}")
    raise ValueError(f"unsupported calc: {calc}")

